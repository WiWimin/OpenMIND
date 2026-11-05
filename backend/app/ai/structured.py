"""结构化输出统一管线。

四段流程：解析预处理 → schema 校验 + 业务字段校验 → 修复重试 → 统一报错与日志。

- 修复重试仅 1 次（首次 + 1 次重试），仍失败时按 `on_failure` 抛 `MODEL_OUTPUT_INVALID`
  或返回 `None` 由调用方降级（见 `docs/ai-design.md 3.3`）。
- 日志只记录场景、尝试次数与校验错误摘要（字段路径 + 规则说明），
  不记录提示词、用户原文或模型原始输出。
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable, Sequence
from typing import Literal, TypeVar, cast, overload

from pydantic import BaseModel, ValidationError

from app.core.exceptions import AppError

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# 修复重试仅 1 次：首次尝试 + 1 次修复重试
MAX_ATTEMPTS = 2
# 修复提示与日志携带的错误条数上限
_MAX_REPORTED_ERRORS = 5
# 单条错误摘要长度上限，避免日志与修复提示膨胀
_MAX_ERROR_CHARS = 160


def normalize_json_text(raw: str) -> str:
    """解析预处理：剥离 markdown 代码块围栏，整体非 JSON 时截取首尾括号范围。"""
    text = (raw or "").strip()
    text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
    text = re.sub(r"\s*```$", "", text).strip()
    if _is_json(text):
        return text
    starts = [index for index in (text.find("{"), text.find("[")) if index != -1]
    ends = [index for index in (text.rfind("}"), text.rfind("]")) if index != -1]
    if starts and ends:
        start, end = min(starts), max(ends)
        if end > start:
            return text[start : end + 1]
    return text


def _is_json(text: str) -> bool:
    try:
        json.loads(text)
    except (ValueError, TypeError):
        return False
    return True


def validation_error_summary(
    exc: ValidationError, *, limit: int = _MAX_REPORTED_ERRORS
) -> list[str]:
    """提取字段路径 + 规则错误（不含模型原始输出），供修复提示与日志使用。"""
    summary: list[str] = []
    for error in exc.errors()[:limit]:
        location = ".".join(str(part) for part in error.get("loc", ())) or "(root)"
        message = str(error.get("msg", "invalid"))[:_MAX_ERROR_CHARS]
        summary.append(f"{location}: {message}")
    return summary


def validate_payload(
    raw: str,
    schema: type[T],
    validator: Callable[[T], Sequence[str]] | None = None,
) -> tuple[T | None, list[str]]:
    """解析预处理 + schema 校验 + 业务字段校验；失败返回 `(None, 错误摘要)`。"""
    try:
        value = schema.model_validate_json(normalize_json_text(raw))
    except ValidationError as exc:
        return None, validation_error_summary(exc)
    if validator is None:
        return value, []
    errors = list(validator(value))[:_MAX_REPORTED_ERRORS]
    if errors:
        return None, errors
    return value, []


def _repair_message(errors: Sequence[str]) -> dict[str, str]:
    detail = "\n".join(f"- {item}" for item in errors) or "- 输出不是合法 JSON 或缺少必需字段"
    return {
        "role": "user",
        "content": (
            "上一次输出未通过校验，请修正以下问题后重新输出："
            "只输出 JSON 本身，不要 markdown 代码块，不要任何额外文字。\n"
            f"需要修正的问题：\n{detail}"
        ),
    }


def _errors_from_app_error(exc: AppError) -> list[str]:
    validation = (exc.details or {}).get("validation")
    if isinstance(validation, list) and validation:
        return [str(item)[:_MAX_ERROR_CHARS] for item in validation[:_MAX_REPORTED_ERRORS]]
    return [exc.message]


def _accept(
    outcome: str | BaseModel,
    schema: type[T],
    validator: Callable[[T], Sequence[str]] | None,
) -> tuple[T | None, list[str]]:
    if isinstance(outcome, str):
        return validate_payload(outcome, schema, validator)
    # chat_json 等已完成 schema 校验的返回（含测试替身对象）：仅做业务字段校验
    if validator is None:
        return cast(T, outcome), []
    errors = list(validator(cast(T, outcome)))[:_MAX_REPORTED_ERRORS]
    if errors:
        return None, errors
    return cast(T, outcome), []


@overload
def run_structured(
    fetch: Callable[[list[dict[str, str]]], str | BaseModel],
    messages: list[dict[str, str]],
    schema: type[T],
    *,
    scene: str,
    validator: Callable[[T], Sequence[str]] | None = ...,
    on_failure: Literal["raise"] = "raise",
) -> T: ...


@overload
def run_structured(
    fetch: Callable[[list[dict[str, str]]], str | BaseModel],
    messages: list[dict[str, str]],
    schema: type[T],
    *,
    scene: str,
    validator: Callable[[T], Sequence[str]] | None = ...,
    on_failure: Literal["degrade"],
) -> T | None: ...


def run_structured(
    fetch: Callable[[list[dict[str, str]]], str | BaseModel],
    messages: list[dict[str, str]],
    schema: type[T],
    *,
    scene: str,
    validator: Callable[[T], Sequence[str]] | None = None,
    on_failure: Literal["raise", "degrade"] = "raise",
) -> T | None:
    """执行结构化输出管线：最多 `MAX_ATTEMPTS` 次尝试（含 1 次修复重试）。

    - `fetch`：返回原始文本（管线负责预处理与校验），或已完成 schema 校验的对象
      （如 `chat_json` 返回值）。
    - `on_failure="raise"`：修复重试后仍失败抛 `MODEL_OUTPUT_INVALID`（502，可重试）。
    - `on_failure="degrade"`：返回 `None`，由调用方降级（如 organize 链返回原文）。
    """
    errors: list[str] = []
    for attempt in range(1, MAX_ATTEMPTS + 1):
        current = messages if attempt == 1 else [*messages, _repair_message(errors)]
        try:
            outcome = fetch(current)
        except AppError as exc:
            # 仅 schema 校验失败（带 validation 详情）进入修复重试；
            # 配置/超时/传输层错误不重试，直接上抛
            if exc.error_code != "MODEL_OUTPUT_INVALID" or "validation" not in (
                exc.details or {}
            ):
                raise
            value = None
            errors = _errors_from_app_error(exc)
        else:
            value, errors = _accept(outcome, schema, validator)
        if value is not None:
            if attempt > 1:
                logger.info("结构化输出经修复重试通过 scene=%s attempt=%d", scene, attempt)
            return cast(T, value)
        logger.warning(
            "结构化输出校验失败 scene=%s attempt=%d errors=%s",
            scene,
            attempt,
            "; ".join(errors) or "-",
        )
    logger.warning(
        "结构化输出修复重试后仍失败 scene=%s attempts=%d on_failure=%s",
        scene,
        MAX_ATTEMPTS,
        on_failure,
    )
    if on_failure == "degrade":
        return None
    raise AppError(
        "MODEL_OUTPUT_INVALID",
        "模型输出校验失败，请重试",
        http_status=502,
        retryable=True,
        details={"validation": errors[:_MAX_REPORTED_ERRORS]},
    )
