from __future__ import annotations

import json

import httpx
import pytest
from pydantic import BaseModel

from app.ai.llm import LLMClient
from app.core.exceptions import AppError

API_BASE = "https://test.local"


class _Echo(BaseModel):
    answer: str


def _client(handler) -> LLMClient:
    return LLMClient(
        api_base=API_BASE,
        api_key="sk-test",
        model="test-model",
        transport=httpx.MockTransport(handler),
    )


def _ok_response(request: httpx.Request, content: str = "正常") -> httpx.Response:
    body = {
        "model": "test-model",
        "choices": [{"message": {"content": content}}],
        "usage": {"prompt_tokens": 7, "completion_tokens": 3},
    }
    return httpx.Response(200, json=body, request=request)


def test_chat_returns_llm_result() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _ok_response(request)

    result = _client(handler).chat([{"role": "user", "content": "你好"}])

    assert result.text == "正常"
    assert result.model == "test-model"
    assert result.usage == {"input": 7, "output": 3}
    assert result.latency_ms >= 0


def test_chat_timeout_retries_then_model_timeout() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        raise httpx.ReadTimeout("timed out", request=request)

    with pytest.raises(AppError) as exc_info:
        _client(handler).chat([{"role": "user", "content": "x"}], timeout_s=0.01)

    assert exc_info.value.error_code == "MODEL_TIMEOUT"
    assert exc_info.value.retryable is True
    assert len(calls) == 3


def test_chat_429_retries_then_rate_limited() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(429, json={}, request=request)

    with pytest.raises(AppError) as exc_info:
        _client(handler).chat([{"role": "user", "content": "x"}])

    assert exc_info.value.error_code == "RATE_LIMITED"
    assert len(calls) == 3


def test_chat_5xx_retries_then_internal_error() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(500, json={}, request=request)

    with pytest.raises(AppError) as exc_info:
        _client(handler).chat([{"role": "user", "content": "x"}])

    assert exc_info.value.error_code == "INTERNAL_ERROR"
    assert exc_info.value.retryable is True
    assert len(calls) == 3


def test_chat_401_fails_without_retry() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(401, json={}, request=request)

    with pytest.raises(AppError) as exc_info:
        _client(handler).chat([{"role": "user", "content": "x"}])

    assert exc_info.value.error_code == "INTERNAL_ERROR"
    assert exc_info.value.retryable is False
    assert len(calls) == 1


def test_chat_invalid_json_raises_model_output_invalid() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not json", request=request)

    with pytest.raises(AppError) as exc_info:
        _client(handler).chat([{"role": "user", "content": "x"}])

    assert exc_info.value.error_code == "MODEL_OUTPUT_INVALID"


def test_chat_empty_choices_raises_model_output_invalid() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": []}, request=request)

    with pytest.raises(AppError) as exc_info:
        _client(handler).chat([{"role": "user", "content": "x"}])

    assert exc_info.value.error_code == "MODEL_OUTPUT_INVALID"


def test_chat_json_validates_schema() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _ok_response(request, content=json.dumps({"answer": "可以"}))

    result = _client(handler).chat_json([{"role": "user", "content": "x"}], schema=_Echo)

    assert isinstance(result, _Echo)
    assert result.answer == "可以"


def test_chat_json_invalid_schema_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _ok_response(request, content='{"wrong": "shape"}')

    with pytest.raises(AppError) as exc_info:
        _client(handler).chat_json([{"role": "user", "content": "x"}], schema=_Echo)

    assert exc_info.value.error_code == "MODEL_OUTPUT_INVALID"


def test_chat_unconfigured_raises_internal_error() -> None:
    client = LLMClient(api_base="", api_key="", model="m")
    with pytest.raises(AppError) as exc_info:
        client.chat([{"role": "user", "content": "x"}])

    assert exc_info.value.error_code == "INTERNAL_ERROR"
