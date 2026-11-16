"""进程内限流：滑动窗口单测 + 中间件/登录防爆破集成行为。

默认用例里 `RATE_LIMIT_ENABLED=false`（见 conftest），这里显式开关覆盖。
"""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.rate_limit import SlidingWindowLimiter, get_limiter


def test_limiter_allows_up_to_limit() -> None:
    limiter = SlidingWindowLimiter()
    assert limiter.hit("k", 3) is None
    assert limiter.hit("k", 3) is None
    assert limiter.hit("k", 3) is None
    blocked = limiter.hit("k", 3)
    assert blocked is not None
    assert blocked >= 1.0


def test_limiter_isolates_keys() -> None:
    limiter = SlidingWindowLimiter()
    limiter.hit("a", 1)
    assert limiter.hit("a", 1) is not None
    assert limiter.hit("b", 1) is None


def test_limiter_window_expires() -> None:
    limiter = SlidingWindowLimiter()
    limiter.hit("k", 1, window_s=0.05)
    assert limiter.hit("k", 1, window_s=0.05) is not None
    time.sleep(0.06)
    assert limiter.hit("k", 1, window_s=0.05) is None


def test_limiter_evicts_when_key_space_full() -> None:
    limiter = SlidingWindowLimiter(max_keys=5)
    for index in range(5):
        limiter.hit(f"key{index}", 100)
    # 第 6 个键触发淘汰，不应抛错
    assert limiter.hit("key5", 100) is None


@pytest.fixture()
def rate_limited_settings(monkeypatch: pytest.MonkeyPatch):
    """打开限流并把阈值压到很小，便于集成断言。"""
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("RATE_LIMIT_LOGIN_PER_MINUTE", "3")
    monkeypatch.setenv("RATE_LIMIT_AI_PER_MINUTE", "2")
    monkeypatch.setenv("RATE_LIMIT_ASR_PER_MINUTE", "1")
    monkeypatch.setenv("RATE_LIMIT_DEFAULT_PER_MINUTE", "4")
    get_settings.cache_clear()
    get_limiter().reset()
    try:
        yield
    finally:
        get_settings.cache_clear()
        get_limiter().reset()


def _register(client: TestClient, name: str) -> dict:
    response = client.post(
        "/api/v1/auth/register", json={"name": name, "password": "password123"}
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


def test_default_limit_returns_429_with_retry_after(client, rate_limited_settings) -> None:
    headers = {"Authorization": f"Bearer {_register(client, 'u1')['access_token']}"}
    statuses = [
        client.get("/api/v1/meetings", headers=headers).status_code
        for _ in range(6)
    ]
    assert 429 in statuses
    blocked = client.get("/api/v1/meetings", headers=headers)
    assert blocked.status_code == 429
    assert blocked.headers.get("Retry-After")
    body = blocked.json()
    assert body["error_code"] == "RATE_LIMITED"
    assert body["retryable"] is True


def test_login_bruteforce_limited(client, rate_limited_settings) -> None:
    _register(client, "victim")
    statuses = []
    for _ in range(4):
        statuses.append(
            client.post(
                "/api/v1/auth/login",
                json={"name": "victim", "password": "wrong-password"},
            ).status_code
        )
    # 前几次进入密码校验（401），随后被限流（注册与登录共享 IP 计数）
    assert 401 in statuses
    assert statuses[-1] == 429
    blocked = client.post(
        "/api/v1/auth/login",
        json={"name": "victim", "password": "wrong-password"},
    )
    assert blocked.status_code == 429
    assert blocked.json()["error_code"] == "RATE_LIMITED"


def test_health_is_exempt_from_rate_limit(client, rate_limited_settings) -> None:
    for _ in range(10):
        assert client.get("/health").status_code == 200


def test_rate_limit_disabled_by_default_config(client) -> None:
    """conftest 默认关闭：密集请求不触发 429。"""
    statuses = [client.get("/api/v1/auth/me").status_code for _ in range(30)]
    assert 429 not in statuses


def test_asr_endpoints_use_dedicated_group(client, rate_limited_settings) -> None:
    """ASR 触发类 POST 单独成组：阈值与 LLM 分开，且带 group 便于排障。"""
    url = "/api/v1/audio/aud_x/retry"

    first = client.post(url)  # 未鉴权 → 401，但已计入 asr 组
    assert first.status_code == 401

    blocked = client.post(url)
    assert blocked.status_code == 429
    body = blocked.json()
    assert body["error_code"] == "RATE_LIMITED"
    assert body["details"]["group"] == "asr"


def test_asr_group_not_consumed_by_read_requests(
    client, rate_limited_settings
) -> None:
    """GET 音频详情不触发转写，不应占用 ASR 配额（asr 组阈值为 1）。"""
    for _ in range(3):
        assert client.get("/api/v1/audio/aud_x").status_code == 401
