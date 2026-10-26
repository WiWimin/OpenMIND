from __future__ import annotations

import json

import httpx
import pytest

from app.ai.embeddings import EmbeddingClient
from app.core.exceptions import AppError

API_BASE = "https://test.local"
DIM = 4


def json_body(request: httpx.Request) -> dict:
    return json.loads(request.content)


def _client(handler, batch_size: int = 16) -> EmbeddingClient:
    return EmbeddingClient(
        api_base=API_BASE,
        api_key="sk-test",
        model="test-embed",
        transport=httpx.MockTransport(handler),
        batch_size=batch_size,
        dim=DIM,
    )


def _ok_response(request: httpx.Request, count: int) -> httpx.Response:
    data = [
        {"index": i, "embedding": [0.1] * DIM}
        for i in range(count)
    ]
    return httpx.Response(200, json={"data": data}, request=request)


def test_embed_returns_vectors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _ok_response(request, count=2)

    vectors = _client(handler).embed(["你好", "世界"])

    assert len(vectors) == 2
    assert all(len(v) == DIM for v in vectors)


def test_embed_requests_configured_dimensions() -> None:
    payloads: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payloads.append(json_body(request))
        return _ok_response(request, count=1)

    _client(handler).embed(["x"])

    assert payloads[0]["dimensions"] == DIM


def test_embed_batches_large_input() -> None:
    batches: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json_body(request)
        batches.append(len(payload["input"]))
        return _ok_response(request, count=len(payload["input"]))

    texts = [f"t{i}" for i in range(40)]
    vectors = _client(handler, batch_size=16).embed(texts)

    assert batches == [16, 16, 8]
    assert len(vectors) == 40


def test_embed_dimension_mismatch_raises_internal_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = {"data": [{"index": 0, "embedding": [0.1, 0.2]}]}
        return httpx.Response(200, json=body, request=request)

    with pytest.raises(AppError) as exc_info:
        _client(handler).embed(["x"])

    assert exc_info.value.error_code == "INTERNAL_ERROR"
    assert exc_info.value.retryable is False


def test_embed_429_retries_then_rate_limited() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(429, json={}, request=request)

    with pytest.raises(AppError) as exc_info:
        _client(handler).embed(["x"])

    assert exc_info.value.error_code == "RATE_LIMITED"
    assert len(calls) == 3


def test_embed_timeout_retries_then_model_timeout() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        raise httpx.ReadTimeout("timed out", request=request)

    with pytest.raises(AppError) as exc_info:
        _client(handler).embed(["x"])

    assert exc_info.value.error_code == "MODEL_TIMEOUT"
    assert len(calls) == 3


def test_embed_empty_input_returns_empty() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        pytest.fail("should not call the transport for empty input")
        return _ok_response(request, 0)

    assert _client(handler).embed([]) == []


def test_embed_unconfigured_raises_model_config_required() -> None:
    client = EmbeddingClient(api_base="", api_key="", model="m")
    with pytest.raises(AppError) as exc_info:
        client.embed(["x"])

    assert exc_info.value.error_code == "MODEL_CONFIG_REQUIRED"


def test_embed_401_raises_model_config_invalid() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={}, request=request)

    with pytest.raises(AppError) as exc_info:
        _client(handler).embed(["x"])

    assert exc_info.value.error_code == "MODEL_CONFIG_INVALID"


def test_embed_402_raises_model_quota_exceeded() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = {"error": {"message": "Insufficient balance"}}
        return httpx.Response(402, json=body, request=request)

    with pytest.raises(AppError) as exc_info:
        _client(handler).embed(["x"])

    assert exc_info.value.error_code == "MODEL_QUOTA_EXCEEDED"


def test_embed_400_quota_body_raises_model_quota_exceeded() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = {
            "error": {
                "message": "Free quota exhausted",
                "type": "AllocationQuota.FreeTierOnly",
            }
        }
        return httpx.Response(400, json=body, request=request)

    with pytest.raises(AppError) as exc_info:
        _client(handler).embed(["x"])

    assert exc_info.value.error_code == "MODEL_QUOTA_EXCEEDED"


def test_embed_403_raises_model_config_invalid() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={}, request=request)

    with pytest.raises(AppError) as exc_info:
        _client(handler).embed(["x"])

    assert exc_info.value.error_code == "MODEL_CONFIG_INVALID"
    assert exc_info.value.retryable is False


def test_embed_5xx_retries_then_internal_error() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(500, json={}, request=request)

    with pytest.raises(AppError) as exc_info:
        _client(handler).embed(["x"])

    assert exc_info.value.error_code == "INTERNAL_ERROR"
    assert exc_info.value.retryable is True
    assert len(calls) == 3
