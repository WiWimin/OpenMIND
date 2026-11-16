"""并发闸门与熔断（app/ai/resilience.py + http_client 接入）。

覆盖：熔断阈值打开 → 快速失败；半开探针 → 恢复闭合；并发排队超时 → 429；
开关关闭（AI_RESILIENCE_ENABLED=false）全部直通；流式路径共用同一状态。
"""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from app.ai import resilience
from app.ai.llm import LLMClient
from app.core import metrics
from app.core.config import get_settings
from app.core.exceptions import AppError

API_BASE = "https://resilience.test/v1"
MODEL = "test-model"


def _client(handler) -> LLMClient:
    return LLMClient(
        api_base=API_BASE,
        api_key="sk-test",
        model=MODEL,
        transport=httpx.MockTransport(handler),
    )


def _ok(request: httpx.Request) -> httpx.Response:
    body = {
        "model": MODEL,
        "choices": [{"message": {"content": "好"}}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1},
    }
    return httpx.Response(200, json=body, request=request)


def _breaker_key() -> str:
    return resilience.breaker_key(API_BASE, MODEL)


# ------------------------------- 熔断器单元 -------------------------------


def test_breaker_opens_after_threshold_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "ai_circuit_failure_threshold", 3)
    breaker = resilience.CircuitBreaker()

    for _ in range(3):
        breaker.record_failure("k")

    assert breaker.state("k") == "open"
    with pytest.raises(AppError) as exc_info:
        breaker.check("k")
    assert exc_info.value.error_code == "MODEL_UPSTREAM_UNAVAILABLE"
    assert exc_info.value.http_status == 503
    assert exc_info.value.retryable is True


def test_breaker_window_expires_old_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "ai_circuit_failure_threshold", 3)
    monkeypatch.setattr(settings, "ai_circuit_window_seconds", 10.0)
    now = {"t": 100.0}
    breaker = resilience.CircuitBreaker(clock=lambda: now["t"])

    breaker.record_failure("k")
    breaker.record_failure("k")
    now["t"] += 60  # 超出窗口，前两次失败应被清出
    breaker.record_failure("k")

    assert breaker.state("k") == "closed"  # 仅 1 次在窗失败，未达阈值
    breaker.record_failure("k")
    breaker.record_failure("k")
    assert breaker.state("k") == "open"


def test_breaker_half_open_probe_recovers_and_failure_reopens(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "ai_circuit_failure_threshold", 2)
    monkeypatch.setattr(settings, "ai_circuit_open_seconds", 30.0)
    now = {"t": 0.0}
    breaker = resilience.CircuitBreaker(clock=lambda: now["t"])

    breaker.record_failure("k")
    breaker.record_failure("k")
    assert breaker.state("k") == "open"

    now["t"] += 31  # 冷却结束
    breaker.check("k")  # 放行第 1 个探针 → half_open
    assert breaker.state("k") == "half_open"
    with pytest.raises(AppError):
        breaker.check("k")  # 半开期间其余请求仍快速失败

    breaker.record_success("k")
    assert breaker.state("k") == "closed"
    breaker.check("k")  # 恢复后正常放行


def test_breaker_probe_failure_reopens(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "ai_circuit_failure_threshold", 2)
    monkeypatch.setattr(settings, "ai_circuit_open_seconds", 30.0)
    now = {"t": 0.0}
    breaker = resilience.CircuitBreaker(clock=lambda: now["t"])

    breaker.record_failure("k")
    breaker.record_failure("k")
    now["t"] += 31
    breaker.check("k")  # 探针
    breaker.record_failure("k")  # 探针失败 → 立即重开

    assert breaker.state("k") == "open"
    with pytest.raises(AppError):
        breaker.check("k")


def test_breaker_ignores_client_side_errors() -> None:
    """4xx/429 不计入熔断：provider 是健康的，问题在请求侧。"""
    breaker = resilience.get_breaker()

    for _ in range(20):
        breaker.check(_breaker_key())  # 从不 record_failure

    assert breaker.state(_breaker_key()) == "closed"


def test_resilience_disabled_passes_through(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "ai_resilience_enabled", False)
    breaker = resilience.get_breaker()
    gate = resilience.get_gate()

    for _ in range(20):
        breaker.record_failure("k")
    breaker.check("k")  # 不抛

    assert gate.acquire("k", timeout_s=0) is True  # 不排队
    gate.release("k")
    assert gate.try_acquire("k") is True
    gate.release("k")


# ------------------------------ 并发闸门单元 ------------------------------


def test_gate_limits_in_flight_and_releases() -> None:
    gate = resilience.get_gate()
    gate.reset()
    key = "gate-test"

    # 默认每 provider 8 个名额：占满后非阻塞获取失败
    held = [gate.try_acquire(key) for _ in range(8)]
    assert all(held)
    assert gate.try_acquire(key) is False

    gate.release(key)
    assert gate.try_acquire(key) is True
    gate.reset()  # 清空（释放剩余名额）


def test_gate_acquire_times_out_and_returns_false() -> None:
    gate = resilience.get_gate()
    gate.reset()
    key = "gate-timeout"

    for _ in range(8):
        assert gate.try_acquire(key) is True

    assert gate.acquire(key, timeout_s=0) is False
    gate.reset()


def test_gate_async_acquire_times_out(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "ai_concurrency_timeout_s", 0.05)
    gate = resilience.get_gate()
    gate.reset()
    key = "gate-async"

    for _ in range(8):
        assert gate.try_acquire(key) is True

    async def run() -> bool:
        return await gate.aacquire(key, timeout_s=0.05)

    assert asyncio.run(run()) is False
    gate.reset()


# --------------------------- 客户端行为集成 ---------------------------


def test_circuit_open_fails_fast_without_http_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "ai_circuit_failure_threshold", 2)
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(500, json={}, request=request)

    client = _client(handler)
    # 第 1 次尝试 500（失败 1）、第 2 次尝试 500（失败 2 → 熔断打开）、
    # 第 3 次尝试被熔断拦下：整次调用以 MODEL_UPSTREAM_UNAVAILABLE 收场
    with pytest.raises(AppError) as first:
        client.chat([{"role": "user", "content": "x"}])
    assert first.value.error_code == "MODEL_UPSTREAM_UNAVAILABLE"
    assert first.value.details and first.value.details["circuit"] == "open"
    assert calls["n"] == 2  # 熔断在第 3 次尝试前打开，不再发包

    with pytest.raises(AppError) as second:
        client.chat([{"role": "user", "content": "x"}])
    assert second.value.error_code == "MODEL_UPSTREAM_UNAVAILABLE"
    assert calls["n"] == 2  # 打开后直接快速失败
    assert metrics.snapshot()["counters"]["ai_circuit_open_total"] == 2
    assert metrics.snapshot()["counters"]["ai_retry_total"] == 1


def test_success_resets_failure_count() -> None:
    breaker = resilience.get_breaker()
    key = _breaker_key()
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(500, json={}, request=request)
        return _ok(request)

    client = _client(handler)
    assert client.chat([{"role": "user", "content": "x"}]).text == "好"
    assert breaker.state(key) == "closed"  # 成功清零，未累计到阈值

    def fail(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={}, request=request)

    # 再来 1 次失败仍不应打开（成功已清零）
    with pytest.raises(AppError):
        _client(fail).chat([{"role": "user", "content": "x"}])
    assert breaker.state(key) == "closed"


def test_concurrency_rejected_returns_rate_limited(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """占满并发名额后，新请求在排队超时时返回 429（scope=concurrency）。"""
    monkeypatch.setattr(get_settings(), "ai_concurrency_timeout_s", 0)
    gate = resilience.get_gate()
    gate.reset()
    gkey = resilience.gate_key(API_BASE)
    for _ in range(8):
        assert gate.try_acquire(gkey) is True

    def handler(request: httpx.Request) -> httpx.Response:
        pytest.fail("熔断/并发拒绝时不应发包")

    with pytest.raises(AppError) as exc_info:
        _client(handler).chat([{"role": "user", "content": "x"}])

    assert exc_info.value.error_code == "RATE_LIMITED"
    assert exc_info.value.http_status == 429
    assert exc_info.value.details and exc_info.value.details["scope"] == "concurrency"
    assert metrics.snapshot()["counters"]["ai_concurrency_rejected_total"] == 1
    gate.reset()


def test_gate_slot_released_after_call(monkeypatch: pytest.MonkeyPatch) -> None:
    """一次调用（含重试）结束后必须归还名额，否则额度会被耗尽。"""
    gate = resilience.get_gate()
    gkey = resilience.gate_key(API_BASE)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={}, request=request)

    with pytest.raises(AppError):
        _client(handler).chat([{"role": "user", "content": "x"}])

    # 3 次尝试若不释放，8 个名额早已耗尽
    held = sum(1 for _ in range(8) if gate.try_acquire(gkey))
    assert held == 8
    gate.reset()


# ------------------------------ 流式路径 ------------------------------


def _sse_body() -> str:
    return (
        "data: "
        + json.dumps(
            {"model": MODEL, "choices": [{"delta": {"content": "你好"}}]},
            ensure_ascii=False,
        )
        + "\n\ndata: [DONE]\n\n"
    )


def _collect(client: LLMClient) -> list[str]:
    async def run() -> list[str]:
        return [
            delta
            async for delta in client.astream_chat([{"role": "user", "content": "x"}])
        ]

    return asyncio.run(run())


def test_stream_success_records_breaker_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, text=_sse_body(), headers={"content-type": "text/event-stream"}
        )

    client = _client(handler)
    assert _collect(client) == ["你好"]
    assert resilience.get_breaker().state(_breaker_key()) == "closed"


def test_stream_5xx_trips_breaker_then_fails_fast(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "ai_circuit_failure_threshold", 2)
    # 首增量前重试的退避压到 0，避免测试等待 1s
    monkeypatch.setattr("app.ai.llm.client.BACKOFF_SECONDS", (0, 0))
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(500, json={}, request=request)

    client = _client(handler)
    with pytest.raises(AppError):
        _collect(client)
    assert calls["n"] == 2  # 首增量前允许 1 次重试 → 共 2 次

    with pytest.raises(AppError) as exc_info:
        _collect(client)
    assert exc_info.value.error_code == "MODEL_UPSTREAM_UNAVAILABLE"
    assert calls["n"] == 2  # 打开后不再发包


def test_stream_generator_exit_only_releases_slot() -> None:
    """消费者提前关闭：释放并发名额，但不计入熔断失败。"""
    gate = resilience.get_gate()
    gkey = resilience.gate_key(API_BASE)
    breaker = resilience.get_breaker()

    def handler(request: httpx.Request) -> httpx.Response:
        # 永不发 [DONE] 的长流，供消费端中途关闭
        payload = "data: " + json.dumps(
            {"model": MODEL, "choices": [{"delta": {"content": "片段"}}]}
        )
        return httpx.Response(
            200, text=payload + "\n\n", headers={"content-type": "text/event-stream"}
        )

    async def run() -> None:
        client = _client(handler)
        async for _delta in client.astream_chat([{"role": "user", "content": "x"}]):
            break  # 收到首个增量即关闭

    asyncio.run(run())

    assert breaker.state(_breaker_key()) == "closed"  # 未记失败
    held = sum(1 for _ in range(8) if gate.try_acquire(gkey))
    assert held == 8  # 名额已归还
    gate.reset()
