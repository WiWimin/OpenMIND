"""AI 连接池（app/ai/connection.py）：按 api_base 复用、按 loop 隔离、可关闭。"""

from __future__ import annotations

import asyncio

import httpx

from app.ai import connection
from app.ai.llm import LLMClient


def test_sync_client_reused_for_same_api_base() -> None:
    first = connection.get_sync_client("https://a.test/v1")
    second = connection.get_sync_client("https://a.test/v1")
    other = connection.get_sync_client("https://b.test/v1")

    assert first is second
    assert first is not other
    assert connection.stats()["sync_clients"] == 2


def test_injected_transport_is_not_pooled() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={}))

    first = connection.get_sync_client("https://a.test/v1", transport=transport)
    second = connection.get_sync_client("https://a.test/v1", transport=transport)

    assert first is not second  # 测试客户端互不串池
    assert connection.stats()["sync_clients"] == 0


def test_llm_client_shares_pooled_http_client() -> None:
    first = LLMClient(api_base="https://llm.test/v1", api_key="k", model="m")
    second = LLMClient(api_base="https://llm.test/v1", api_key="k", model="m")
    other_host = LLMClient(api_base="https://other.test/v1", api_key="k", model="m")

    assert first._client is second._client
    assert first._client is not other_host._client


def test_close_ai_clients_is_idempotent() -> None:
    client = connection.get_sync_client("https://a.test/v1")
    connection.close_ai_clients()
    connection.close_ai_clients()  # 重复关闭不报错

    assert connection.stats()["sync_clients"] == 0
    assert client.is_closed


def test_async_client_is_scoped_to_event_loop() -> None:
    """AsyncClient 不跨事件循环复用（测试各自独立 loop，跨用复用会报绑定错误）。"""

    async def acquire_and_count() -> tuple[httpx.AsyncClient, dict[str, int]]:
        client = connection.get_async_client("https://llm.test/v1")
        return client, connection.stats()

    first_loop_client, first_stats = asyncio.run(acquire_and_count())
    second_loop_client, second_stats = asyncio.run(acquire_and_count())

    assert first_loop_client is not second_loop_client
    # 各自 loop 内都是 1 个共享客户端（不同 loop 之间不复用）
    assert first_stats["async_clients"] == 1
    assert second_stats["async_clients"] == 1

    async def close() -> None:
        await connection.aclose_ai_clients()

    asyncio.run(close())


def test_pool_disabled_builds_fresh_client(monkeypatch) -> None:
    """`AI_CONNECTION_POOL_ENABLED=false` 时按次新建（回滚开关）。"""
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "ai_connection_pool_enabled", False)

    first = connection.get_sync_client("https://a.test/v1")
    second = connection.get_sync_client("https://a.test/v1")

    assert first is not second
    assert connection.stats()["sync_clients"] == 0
    first.close()
    second.close()
