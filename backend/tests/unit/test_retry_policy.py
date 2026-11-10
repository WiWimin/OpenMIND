"""重试策略（app/ai/retry.py + http_client 分级重试）：幂等分级、退避、Deadline、Retry-After。"""

from __future__ import annotations

import datetime as dt
import random
from email.utils import format_datetime

import httpx
import pytest

import app.ai.http_client as http_client
from app.ai.http_client import ModelHTTPClient
from app.ai.llm import LLMClient
from app.ai.retry import MAX_RETRY_AFTER_S, RetryPolicy, parse_retry_after
from app.core.exceptions import AppError

API_BASE = "https://test.local/v1"


def _client(handler, **kwargs) -> LLMClient:
    return LLMClient(
        api_base=API_BASE,
        api_key="sk-test",
        model="test-model",
        transport=httpx.MockTransport(handler),
        **kwargs,
    )


# ------------------------------- 策略单元 -------------------------------


def test_retry_after_parses_seconds() -> None:
    assert parse_retry_after("2") == 2.0
    assert parse_retry_after(" 1.5 ") == 1.5
    assert parse_retry_after("0") == 0.0
    assert parse_retry_after(None) is None
    assert parse_retry_after("") is None
    assert parse_retry_after("not-a-number") is None
    assert parse_retry_after("-3") is None


def test_retry_after_parses_http_date_and_caps() -> None:
    future = format_datetime(dt.datetime.now(dt.UTC) + dt.timedelta(seconds=90))
    value = parse_retry_after(future)
    assert value is not None
    assert 0 < value <= MAX_RETRY_AFTER_S  # 异常大的等待被截断

    past = format_datetime(dt.datetime.now(dt.UTC) - dt.timedelta(seconds=5))
    assert parse_retry_after(past) is None  # 过去的时间视为无效


def test_backoff_grows_exponentially_with_jitter() -> None:
    policy = RetryPolicy()
    rng = random.Random(7)

    for _ in range(20):
        first = policy.delay_for(1, rng=rng)
        second = policy.delay_for(2, rng=rng)
        third = policy.delay_for(3, rng=rng)
        assert 0.5 <= first <= 1.5  # 1s * 0.5–1.5
        assert 1.5 <= second <= 4.5  # 3s * 0.5–1.5
        assert 1.5 <= third <= 4.5  # 第 3 次起封顶 3s * 0.5–1.5


def test_backoff_respects_retry_after() -> None:
    policy = RetryPolicy()
    rng = random.Random(7)

    delay = policy.delay_for(1, retry_after_s=6.0, rng=rng)
    assert delay >= 6.0  # 服务端要求的等待优先于本地退避


def test_policy_allows_matrix_for_non_idempotent_call() -> None:
    policy = RetryPolicy(retry_ambiguous=False)

    assert policy.allows("connect") is True  # 未送达 → 可重试
    assert policy.allows("timeout") is False  # 已送达未知 → 不重传
    assert policy.allows("transport") is False
    assert policy.allows("http_429") is True
    assert policy.allows("http_5xx") is True
    assert policy.allows("http") is False  # 4xx 语义错误
    assert policy.allows("http_429", retryable=False) is False


def test_policy_allows_timeout_for_idempotent_call() -> None:
    policy = RetryPolicy(retry_ambiguous=True)

    assert policy.allows("timeout") is True
    assert policy.allows("transport") is True


# --------------------------- 客户端行为集成 ---------------------------


def test_read_timeout_does_not_retry_but_connect_error_does() -> None:
    read_calls: list[httpx.Request] = []

    def read_timeout(request: httpx.Request) -> httpx.Response:
        read_calls.append(request)
        raise httpx.ReadTimeout("timed out", request=request)

    with pytest.raises(AppError) as exc_info:
        _client(read_timeout).chat([{"role": "user", "content": "x"}])
    assert exc_info.value.error_code == "MODEL_TIMEOUT"
    assert len(read_calls) == 1

    connect_calls: list[httpx.Request] = []

    def connect_error(request: httpx.Request) -> httpx.Response:
        connect_calls.append(request)
        raise httpx.ConnectError("refused", request=request)

    with pytest.raises(AppError):
        _client(connect_error).chat([{"role": "user", "content": "x"}])
    assert len(connect_calls) == 3


def test_backoff_sleeps_recorded_without_real_wait() -> None:
    """假时钟（conftest `_no_real_backoff`）记录退避等待，不在测试里真睡。"""
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(500, json={}, request=request)

    with pytest.raises(AppError):
        _client(handler).chat([{"role": "user", "content": "x"}])

    sleeps: list[float] = http_client.time.sleeps
    assert len(calls) == 3
    assert len(sleeps) == 2
    assert all(0.5 <= value <= 4.5 for value in sleeps)


def test_429_honors_retry_after_in_backoff() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429, json={"error": {"code": "rate_limit"}}, headers={"Retry-After": "3"}
        )

    with pytest.raises(AppError) as exc_info:
        _client(handler).chat([{"role": "user", "content": "x"}])

    assert exc_info.value.error_code == "RATE_LIMITED"
    # 错误体透出等待时长，供前端与日志使用
    assert exc_info.value.details and exc_info.value.details["retry_after_s"] == 3.0
    assert all(value >= 3.0 for value in http_client.time.sleeps)


def test_non_retryable_error_never_sleeps() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={}, request=request)

    with pytest.raises(AppError) as exc_info:
        _client(handler).chat([{"role": "user", "content": "x"}])

    assert exc_info.value.error_code == "MODEL_CONFIG_INVALID"
    assert http_client.time.sleeps == []


def test_deadline_stops_further_attempts() -> None:
    """全局 deadline：预算耗尽后不再发起新尝试，直接返回最后一次错误。"""
    fake_time = http_client.time  # conftest 注入的假时钟
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        fake_time.now += 60  # 单次尝试耗尽大半预算
        return httpx.Response(500, json={}, request=request)

    with pytest.raises(AppError) as exc_info:
        _client(handler).chat([{"role": "user", "content": "x"}])

    assert exc_info.value.error_code == "INTERNAL_ERROR"
    assert len(calls) == 2  # 第 3 次尝试会被 deadline 拦下
    assert len(fake_time.sleeps) == 1  # 仅 1 次退避


def test_idempotent_client_retries_read_timeout() -> None:
    """Embedding 幂等：读超时可安全重发，仍保持 3 次尝试。"""
    from app.ai.embeddings import EmbeddingClient

    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        raise httpx.ReadTimeout("timed out", request=request)

    client = EmbeddingClient(
        api_base=API_BASE,
        api_key="sk-test",
        model="embed",
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(AppError):
        client.embed(["x"])

    assert len(calls) == 3


def test_default_policy_has_no_deadline_for_asr() -> None:
    """ASR 单次 120s：不设全局 deadline（否则首轮即被 90s 预算截断）。"""
    from app.ai.transcription import TranscriptionClient

    client = TranscriptionClient(
        api_base=API_BASE, api_key="k", model="asr", transport=httpx.MockTransport(None)
    )
    assert client.idempotent is False
    assert client.retry_policy.deadline_s is None
    assert client.retry_policy.retry_ambiguous is False


def test_deadline_defaults_to_settings_for_llm() -> None:
    client = _client(lambda request: httpx.Response(200, json={"choices": []}))
    assert client.retry_policy.deadline_s == 90.0


def test_sender_receives_attempt_timeout_budget() -> None:
    """基类契约：`send` 接收本次尝试的超时预算（受 deadline 收窄）。"""
    budgets: list[float] = []

    client = ModelHTTPClient(
        api_base=API_BASE,
        api_key="k",
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={})),
    )

    response = client._request_with_retry(  # noqa: SLF012 — 直接验证基类契约
        lambda attempt_timeout: (
            budgets.append(attempt_timeout),
            httpx.Response(200, json={}, request=httpx.Request("POST", f"{API_BASE}/x")),
        )[-1],
        timeout_s=12,
    )

    assert response.status_code == 200
    assert budgets == [12]  # 无 deadline 时按调用方超时
    assert client.retry_policy.deadline_s is None  # 幂等基类默认不设 deadline
