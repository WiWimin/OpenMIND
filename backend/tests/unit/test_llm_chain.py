"""LLM 降级链（ai/llm/chain.py）：候选构造、触发类别、chat/astream 接入。"""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from app.ai.llm import LLMClient
from app.ai.llm.chain import (
    MAX_CHAIN_LENGTH,
    build_chain,
    configured_chain,
    parse_fallback_models,
    should_fall_back,
)
from app.core import metrics
from app.core.config import get_settings
from app.core.exceptions import AppError

API_BASE = "https://chain.test/v1"


def _ok_body(model: str) -> dict:
    return {
        "model": model,
        "choices": [{"message": {"content": f"来自{model}"}}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1},
    }


def _client(handler, model: str = "primary-model") -> LLMClient:
    return LLMClient(
        api_base=API_BASE,
        api_key="sk-test",
        model=model,
        transport=httpx.MockTransport(handler),
    )


# ------------------------------- 链构造 -------------------------------


def test_parse_fallback_models_trims_and_dedupes() -> None:
    assert parse_fallback_models(" a , b,,a ,  ") == ["a", "b"]
    assert parse_fallback_models("") == []
    assert parse_fallback_models(None) == []  # type: ignore[arg-type]


def test_build_chain_dedupes_primary_and_caps_length() -> None:
    chain = build_chain("m1", ["m1", "m2", "m3", "m4", "m5"])
    assert chain[0] == "m1"
    assert len(chain) == MAX_CHAIN_LENGTH
    assert len(set(chain)) == len(chain)


def test_configured_chain_reads_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "llm_fallback_models", "fb1, fb2")
    assert configured_chain("primary") == ["primary", "fb1", "fb2"]
    monkeypatch.setattr(get_settings(), "llm_fallback_models", "")
    assert configured_chain("primary") == ["primary"]


def test_should_fall_back_only_model_specific_codes() -> None:
    def err(code: str) -> AppError:
        return AppError(code, "x", http_status=500)

    for code in (
        "MODEL_QUOTA_EXCEEDED",
        "MODEL_INPUT_TOO_LONG",
        "MODEL_UPSTREAM_UNAVAILABLE",
        "MODEL_TIMEOUT",
    ):
        assert should_fall_back(err(code)), code
    for code in (
        "MODEL_CONFIG_INVALID",
        "RATE_LIMITED",
        "INTERNAL_ERROR",
        "MODEL_OUTPUT_INVALID",
    ):
        assert not should_fall_back(err(code)), code


# --------------------------- chat 接入降级 ---------------------------


def test_chat_falls_back_on_quota_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "llm_fallback_models", "backup-model")
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        calls.append(body["model"])
        if body["model"] == "primary-model":
            return httpx.Response(402, json={"error": {"code": "insufficient_quota"}})
        return httpx.Response(200, json=_ok_body(body["model"]))

    result = _client(handler).chat([{"role": "user", "content": "x"}])

    assert calls == ["primary-model", "backup-model"]
    assert result.model == "backup-model"
    assert "backup-model" in result.text
    assert metrics.snapshot()["counters"]["ai_fallback_total"] == 1


def test_chat_no_fall_back_on_config_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    """密钥问题对所有模型一致，不浪费备用模型调用。"""
    monkeypatch.setattr(get_settings(), "llm_fallback_models", "backup-model")
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        calls.append(body["model"])
        return httpx.Response(401, json={"error": {"message": "bad key"}})

    with pytest.raises(AppError) as exc_info:
        _client(handler).chat([{"role": "user", "content": "x"}])

    assert exc_info.value.error_code == "MODEL_CONFIG_INVALID"
    assert calls == ["primary-model"]  # 未降级
    assert metrics.snapshot().get("counters", {}).get("ai_fallback_total", 0) == 0


def test_chat_all_candidates_fail_raises_last_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "llm_fallback_models", "backup-model")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(402, json={"error": {"code": "insufficient_quota"}})

    with pytest.raises(AppError) as exc_info:
        _client(handler).chat([{"role": "user", "content": "x"}])

    assert exc_info.value.error_code == "MODEL_QUOTA_EXCEEDED"


def test_chat_without_fallback_env_single_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "llm_fallback_models", "")
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(402, json={"error": {"code": "insufficient_quota"}})

    with pytest.raises(AppError):
        _client(handler).chat([{"role": "user", "content": "x"}])
    assert calls["n"] == 1


def test_chat_scene_params_applied(monkeypatch: pytest.MonkeyPatch) -> None:
    """rag_judge 场景：温度 0、max_tokens 16 由场景注册表下发。"""
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content))
        return httpx.Response(200, json=_ok_body("m"))

    _client(handler).chat([{"role": "user", "content": "x"}], scene="rag_judge")

    assert seen["temperature"] == 0.0
    assert seen["max_tokens"] == 16


def test_chat_scene_input_limit_rejects_before_send(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """rag_judge 上限 4000：超限在发送前拒绝，不发 HTTP 请求。"""

    def handler(request: httpx.Request) -> httpx.Response:
        pytest.fail("超限输入不应发包")

    client = _client(handler)
    big = [{"role": "user", "content": "中" * 5000}]
    with pytest.raises(AppError) as exc_info:
        client.chat(big, scene="rag_judge")

    assert exc_info.value.error_code == "MODEL_INPUT_TOO_LONG"
    assert exc_info.value.http_status == 413


# --------------------------- 流式接入降级 ---------------------------


def _sse(model: str) -> str:
    event = {"model": model, "choices": [{"delta": {"content": f"来自{model}"}}]}
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\ndata: [DONE]\n\n"


def test_stream_falls_back_before_first_delta(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "llm_fallback_models", "backup-model")
    monkeypatch.setattr("app.ai.llm.client.BACKOFF_SECONDS", (0, 0))
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        calls.append(body["model"])
        if body["model"] == "primary-model":
            return httpx.Response(402, json={"error": {"code": "insufficient_quota"}})
        return httpx.Response(
            200, text=_sse(body["model"]), headers={"content-type": "text/event-stream"}
        )

    client = _client(handler)

    async def run() -> list[str]:
        return [
            d
            async for d in client.astream_chat([{"role": "user", "content": "x"}])
        ]

    deltas = asyncio.run(run())
    assert calls == ["primary-model", "backup-model"]
    assert deltas == ["来自backup-model"]


def test_stream_input_limit_rejects_before_send(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        pytest.fail("超限输入不应发包")

    client = _client(handler)
    big = [{"role": "user", "content": "中" * 5000}]

    async def run() -> None:
        async for _ in client.astream_chat(big, scene="rag_judge"):
            pass

    with pytest.raises(AppError) as exc_info:
        asyncio.run(run())
    assert exc_info.value.error_code == "MODEL_INPUT_TOO_LONG"
