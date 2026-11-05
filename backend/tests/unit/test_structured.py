from __future__ import annotations

import logging

import pytest
from pydantic import BaseModel, Field

from app.ai.structured import (
    MAX_ATTEMPTS,
    normalize_json_text,
    run_structured,
    validate_payload,
)
from app.core.exceptions import AppError


class Item(BaseModel):
    name: str = Field(min_length=1)
    priority: str = "medium"


class Result(BaseModel):
    items: list[Item]


class FakeClient:
    """按脚本返回的 chat_json 替身（对象返回路径）。"""

    def __init__(self, script: list[object]) -> None:
        self.script = script
        self.calls: list[list[dict[str, str]]] = []

    def chat_json(self, messages, *, schema, **kwargs):  # noqa: ANN001, ANN003
        self.calls.append(messages)
        outcome = self.script[min(len(self.calls) - 1, len(self.script) - 1)]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


# ---------- 解析预处理 ----------


def test_normalize_strips_markdown_fence() -> None:
    raw = '```json\n{"items": [{"name": "a"}]}\n```'
    assert normalize_json_text(raw) == '{"items": [{"name": "a"}]}'


def test_normalize_extracts_bracket_span_with_prose() -> None:
    raw = '好的，以下是结果：\n{"items": [{"name": "a"}]}\n希望有帮助'
    assert normalize_json_text(raw) == '{"items": [{"name": "a"}]}'


def test_normalize_keeps_valid_json_untouched() -> None:
    raw = '{"items": [{"name": "中文 a"}]}'
    assert normalize_json_text(raw) == raw


def test_validate_payload_accepts_fenced_json() -> None:
    value, errors = validate_payload('```json\n{"items": [{"name": "a"}]}\n```', Result)

    assert errors == []
    assert value is not None
    assert value.items[0].name == "a"


def test_validate_payload_reports_field_paths_on_schema_failure() -> None:
    value, errors = validate_payload('{"items": [{"name": ""}]}', Result)

    assert value is None
    assert errors
    assert any("name" in error for error in errors)


def test_validate_payload_business_validator_failure() -> None:
    def validator(result: Result) -> list[str]:
        return [f"items.{i}.priority 非法" for i, _ in enumerate(result.items)]

    value, errors = validate_payload(
        '{"items": [{"name": "a", "priority": "urgent"}]}', Result, validator
    )

    assert value is None
    assert "items.0.priority 非法" in errors


# ---------- 修复重试：仅 1 次 ----------


def test_retry_after_invalid_first_output() -> None:
    client = FakeClient(["抱歉，无法完成", '{"items": [{"name": "a"}]}'])

    result = run_structured(
        lambda msgs: client.chat_json(msgs, schema=Result),
        [{"role": "user", "content": "任务"}],
        Result,
        scene="unit_retry",
    )

    assert len(client.calls) == 2
    assert result.items[0].name == "a"
    # 第二次调用携带修复消息与首次错误
    repair = client.calls[1][-1]
    assert repair["role"] == "user"
    assert "上一次输出未通过校验" in repair["content"]


def test_exactly_one_retry_then_raise() -> None:
    client = FakeClient(["完全不是 JSON"])
    seen: list[int] = []

    def fetch(messages):  # noqa: ANN001
        seen.append(len(messages))
        return client.chat_json(messages, schema=Result)

    with pytest.raises(AppError) as exc_info:
        run_structured(
            fetch,
            [{"role": "user", "content": "任务"}],
            Result,
            scene="unit_raise",
        )

    assert len(seen) == MAX_ATTEMPTS  # 首次 + 1 次修复重试，共 2 次
    assert exc_info.value.error_code == "MODEL_OUTPUT_INVALID"
    assert exc_info.value.http_status == 502
    assert exc_info.value.retryable is True
    # 统一报错 details 仅含字段级错误，不含模型原文与提示词
    details = exc_info.value.details or {}
    assert "validation" in details
    assert "完全不是 JSON" not in str(details)


def test_degrade_returns_none_after_failed_retry() -> None:
    client = FakeClient(['{"items": [{"name": ""}]}'])

    result = run_structured(
        lambda msgs: client.chat_json(msgs, schema=Result),
        [{"role": "user", "content": "任务"}],
        Result,
        scene="unit_degrade",
        on_failure="degrade",
    )

    assert result is None
    assert len(client.calls) == MAX_ATTEMPTS


def test_business_validation_failure_triggers_retry_then_pass() -> None:
    def validator(result: Result) -> list[str]:
        errors = []
        for index, item in enumerate(result.items):
            if item.priority not in {"high", "medium", "low"}:
                errors.append(f"items.{index}.priority 非法")
        return errors

    client = FakeClient(
        [
            Result(items=[Item(name="a", priority="urgent")]),
            Result(items=[Item(name="a", priority="high")]),
        ]
    )

    result = run_structured(
        lambda msgs: client.chat_json(msgs, schema=Result),
        [{"role": "user", "content": "任务"}],
        Result,
        scene="unit_biz_retry",
        validator=validator,
    )

    assert len(client.calls) == 2
    assert result.items[0].priority == "high"


def test_business_validation_failure_degrades_when_retry_also_fails() -> None:
    def validator(result: Result) -> list[str]:
        return [f"items.{i}.priority 非法" for i, _ in enumerate(result.items)]

    client = FakeClient([Result(items=[Item(name="a", priority="urgent")])])

    result = run_structured(
        lambda msgs: client.chat_json(msgs, schema=Result),
        [{"role": "user", "content": "任务"}],
        Result,
        scene="unit_biz_degrade",
        validator=validator,
        on_failure="degrade",
    )

    assert result is None
    assert len(client.calls) == MAX_ATTEMPTS


# ---------- 错误分类：仅输出校验错误进入重试 ----------


def test_config_error_propagates_without_retry() -> None:
    calls: list[int] = []

    def fetch(messages):  # noqa: ANN001
        calls.append(len(messages))
        raise AppError("MODEL_CONFIG_REQUIRED", "未配置大模型（LLM）", http_status=400)

    with pytest.raises(AppError) as exc_info:
        run_structured(fetch, [{"role": "user", "content": "x"}], Result, scene="unit_cfg")

    assert exc_info.value.error_code == "MODEL_CONFIG_REQUIRED"
    assert len(calls) == 1


def test_output_invalid_without_validation_detail_propagates() -> None:
    """chat_json 之前的传输层输出错误（无 validation 详情）不进入修复重试。"""

    def fetch(messages):  # noqa: ANN001
        raise AppError("MODEL_OUTPUT_INVALID", "模型输出无法解析", http_status=502)

    with pytest.raises(AppError) as exc_info:
        run_structured(fetch, [{"role": "user", "content": "x"}], Result, scene="unit_transport")

    assert exc_info.value.error_code == "MODEL_OUTPUT_INVALID"
    assert exc_info.value.details is None


def test_error_details_from_chat_json_drive_repair_message() -> None:
    """chat_json 校验失败附带 validation 详情 → 进入修复重试并注入错误摘要。"""

    def fetch(messages):  # noqa: ANN001
        if len(messages) == 1:
            raise AppError(
                "MODEL_OUTPUT_INVALID",
                "模型输出无法解析",
                http_status=502,
                details={"validation": ["items.0.name: Field required"]},
            )
        return Result(items=[Item(name="补救")])

    result = run_structured(fetch, [{"role": "user", "content": "x"}], Result, scene="unit_detail")

    assert result.items[0].name == "补救"


# ---------- 规范日志：不含提示词与模型原文 ----------


def test_logs_exclude_prompt_and_model_raw_output(
    caplog: pytest.LogCaptureFixture,
) -> None:
    secret_prompt = "系统机密提示词-不得外泄"
    model_raw = "模型原始输出-SHOULD_NOT_APPEAR"

    with caplog.at_level(logging.WARNING, logger="app.ai.structured"):
        run_structured(
            lambda msgs: model_raw,  # 永远返回不可解析的原文
            [{"role": "user", "content": secret_prompt}],
            Result,
            scene="unit_log",
            on_failure="degrade",
        )

    text = "\n".join(record.getMessage() for record in caplog.records)
    assert "unit_log" in text  # 场景标识存在
    assert secret_prompt not in text
    assert model_raw not in text


def test_repair_message_contains_field_errors_only() -> None:
    client = FakeClient(['{"items": [{"name": ""}]}', '{"items": [{"name": "b"}]}'])

    run_structured(
        lambda msgs: client.chat_json(msgs, schema=Result),
        [{"role": "user", "content": "任务正文"}],
        Result,
        scene="unit_repair_content",
    )

    repair_content = client.calls[1][-1]["content"]
    assert "items" in repair_content  # 字段错误摘要
    assert "任务正文" not in repair_content  # 不回显用户原文


def test_first_attempt_messages_not_mutated() -> None:
    client = FakeClient(["无效", '{"items": [{"name": "a"}]}'])
    original: list[dict[str, str]] = [{"role": "user", "content": "任务"}]
    snapshot = list(original)

    run_structured(
        lambda msgs: client.chat_json(msgs, schema=Result),
        original,
        Result,
        scene="unit_immutability",
    )

    assert original == snapshot
    assert len(client.calls[0]) == 1
