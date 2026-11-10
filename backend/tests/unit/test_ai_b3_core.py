"""B3 错误细分 / 输入预检 / 场景注册表（ai/errors.py、ai/tokens.py、ai/scenes.py）。"""

from __future__ import annotations

import httpx
import pytest

from app.ai import errors as ai_errors
from app.ai.scenes import get_scene, scene_purpose
from app.ai.tokens import (
    ensure_input_within_limit,
    estimate_messages_tokens,
    estimate_tokens,
)
from app.core.exceptions import AppError
from app.schemas.model_config import ModelPurpose

SERVICE = "模型服务"


def _resp(status: int, json_body: dict | None = None, text: str = "") -> httpx.Response:
    request = httpx.Request("POST", "https://x.test/v1/chat/completions")
    if json_body is not None:
        return httpx.Response(status, json=json_body, request=request)
    return httpx.Response(status, text=text, request=request)


# ------------------------------- errors.py -------------------------------


def test_context_length_body_maps_to_input_too_long() -> None:
    response = _resp(
        400,
        {"error": {"code": "context_length_exceeded", "message": "too many tokens"}},
    )
    error = ai_errors.classify_error(response, service_label=SERVICE)

    assert error.error_code == "MODEL_INPUT_TOO_LONG"
    assert error.http_status == 413
    assert error.retryable is False
    assert error.details == {"reason": "context_length"}


def test_413_status_maps_to_input_too_long() -> None:
    error = ai_errors.classify_error(_resp(413), service_label=SERVICE)
    assert error.error_code == "MODEL_INPUT_TOO_LONG"
    assert error.http_status == 413


def test_model_not_found_body_maps_to_config_invalid_with_reason() -> None:
    response = _resp(
        400, {"error": {"code": "model_not_found", "message": "does not exist"}}
    )
    error = ai_errors.classify_error(response, service_label=SERVICE)

    assert error.error_code == "MODEL_CONFIG_INVALID"
    assert error.details == {"reason": "model_not_found"}


def test_status_mapping_unchanged_for_common_cases() -> None:
    assert (
        ai_errors.classify_error(_resp(429), service_label=SERVICE).error_code
        == "RATE_LIMITED"
    )
    assert (
        ai_errors.classify_error(_resp(503), service_label=SERVICE).error_code
        == "INTERNAL_ERROR"
    )
    assert (
        ai_errors.classify_error(_resp(401), service_label=SERVICE).error_code
        == "MODEL_CONFIG_INVALID"
    )
    quota = ai_errors.classify_error(
        _resp(400, text="insufficient quota for this key"), service_label=SERVICE
    )
    assert quota.error_code == "MODEL_QUOTA_EXCEEDED"
    assert quota.http_status == 402


def test_generic_400_still_config_invalid() -> None:
    error = ai_errors.classify_error(_resp(400, text="bad request"), service_label=SERVICE)
    assert error.error_code == "MODEL_CONFIG_INVALID"
    assert error.http_status == 400


def test_quota_hint_does_not_mask_context_length() -> None:
    """含“额度”字样的超长错误仍应判为输入超长（更具体的语义）。"""
    response = _resp(400, text="context length exceeded, 额度不足")
    error = ai_errors.classify_error(response, service_label=SERVICE)
    assert error.error_code == "MODEL_INPUT_TOO_LONG"


# ------------------------------- tokens.py -------------------------------


def test_estimate_tokens_counts_cjk_and_ascii() -> None:
    assert estimate_tokens("") == 0
    assert estimate_tokens("你好世界") == 4  # CJK 1 字 ≈ 1 token
    assert estimate_tokens("abcdefgh") == 2  # 4 字符 ≈ 1 token
    assert estimate_tokens("你好ab") == 3


def test_estimate_messages_adds_per_message_overhead() -> None:
    messages = [
        {"role": "system", "content": "规则"},
        {"role": "user", "content": "问题"},
    ]
    # 每条 4 开销 + 内容 2
    assert estimate_messages_tokens(messages) == 12


def test_ensure_input_within_limit_passes_when_under(monkeypatch) -> None:
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "ai_input_token_limit", 100)
    assert ensure_input_within_limit([{"role": "user", "content": "你好"}]) == 6


def test_ensure_input_raises_input_too_long_when_over(monkeypatch) -> None:
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "ai_input_token_limit", 5)
    long_input = [{"role": "user", "content": "这是一段明显超过五个token的输入内容"}]
    with pytest.raises(AppError) as exc_info:
        ensure_input_within_limit(long_input)

    assert exc_info.value.error_code == "MODEL_INPUT_TOO_LONG"
    assert exc_info.value.http_status == 413
    assert exc_info.value.details and exc_info.value.details["limit"] == 5


def test_scene_limit_overrides_global(monkeypatch) -> None:
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "ai_input_token_limit", 5)
    # 场景上限 4000 > 实际输入 → 放行
    assert ensure_input_within_limit(
        [{"role": "user", "content": "这是一段明显超过五个token的输入内容"}],
        scene_limit=4_000,
    ) > 5


def test_zero_limit_disables_precheck(monkeypatch) -> None:
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "ai_input_token_limit", 0)
    assert ensure_input_within_limit([{"role": "user", "content": "很长" * 10000}]) == 0


# ------------------------------- scenes.py -------------------------------


def test_known_scene_returns_spec() -> None:
    judge = get_scene("rag_judge")
    assert judge.temperature == 0.0
    assert judge.max_tokens == 16
    assert judge.input_token_limit == 4_000

    template = get_scene("template_draft")
    assert template.temperature == 0.4
    assert template.purpose is ModelPurpose.minutes


def test_unknown_or_empty_scene_falls_back_to_default() -> None:
    default = get_scene(None)
    assert default.name == "default"
    assert default.temperature == 0.2
    assert get_scene("not_exists").name == "default"


def test_scene_purpose_mapping() -> None:
    assert scene_purpose("minutes") is ModelPurpose.minutes
    assert scene_purpose("extract_issues") is ModelPurpose.extraction
    assert scene_purpose("rag_judge") is None  # Judge 不做用途覆盖
    assert scene_purpose("unknown") is None
