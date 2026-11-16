"""AI 模型调用的 HTTP 连接池。

解决「按请求新建 httpx.Client → 每次调用都做一遍 TCP/TLS 握手」的问题：

- 同步 `httpx.Client` 按 `api_base` 进程级共享（线程安全），开启 keep-alive
  复用连接；`Authorization` 仍逐请求注入，不进池键，密钥不落池。
- 异步 `httpx.AsyncClient` 按「事件循环 + api_base」共享（`WeakKeyDictionary`），
  避免跨事件循环复用报错——测试各自独立 loop，旧 loop 结束后其客户端随弱引用回收。
- 注入 `transport`（测试 `MockTransport`）或 `AI_CONNECTION_POOL_ENABLED=false`
  时不进池、按次新建，保证测试隔离与可回滚。
- 关闭：应用 lifespan 调 `aclose_ai_clients()`；仅同步池用 `close_ai_clients()`。
"""

from __future__ import annotations

import asyncio
import logging
import threading
import weakref

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_sync_clients: dict[str, httpx.Client] = {}
# key = 事件循环 + api_base：同一个 loop 内复用，跨 loop 不复用
_async_pools: weakref.WeakKeyDictionary[
    asyncio.AbstractEventLoop, dict[str, httpx.AsyncClient]
] = weakref.WeakKeyDictionary()
_lock = threading.Lock()


def _enabled() -> bool:
    return get_settings().ai_connection_pool_enabled


def _limits() -> httpx.Limits:
    settings = get_settings()
    return httpx.Limits(
        max_connections=max(1, settings.ai_max_connections),
        max_keepalive_connections=max(1, settings.ai_max_keepalive_connections),
        keepalive_expiry=max(1.0, settings.ai_keepalive_expiry_s),
    )


def pooled(transport: httpx.BaseTransport | None = None) -> bool:
    """该 transport 是否走池化共享客户端。"""
    return transport is None and _enabled()


def get_sync_client(
    api_base: str, *, transport: httpx.BaseTransport | None = None
) -> httpx.Client:
    """取按 `api_base` 共享的同步客户端；注入 transport 或关闭池时按次新建。"""
    if not pooled(transport):
        return httpx.Client(base_url=api_base, transport=transport, limits=_limits())
    with _lock:
        client = _sync_clients.get(api_base)
        if client is None:
            client = httpx.Client(base_url=api_base, limits=_limits())
            _sync_clients[api_base] = client
            logger.debug("AI 同步客户端已创建并缓存 host=%s", api_base)
        return client


def get_async_client(
    api_base: str, *, transport: httpx.BaseTransport | None = None
) -> httpx.AsyncClient:
    """取当前事件循环内按 `api_base` 共享的异步客户端。"""
    if not pooled(transport):
        return httpx.AsyncClient(base_url=api_base, transport=transport, limits=_limits())
    loop = asyncio.get_running_loop()
    with _lock:
        clients = _async_pools.get(loop)
        if clients is None:
            # 事件循环已关闭的池条目无法再用（aclose 需要原 loop），直接丢弃交给 GC
            for stale in [
                key for key in list(_async_pools) if key is not loop and key.is_closed()
            ]:
                _async_pools.pop(stale, None)
            clients = {}
            _async_pools[loop] = clients
        client = clients.get(api_base)
        if client is None:
            client = httpx.AsyncClient(base_url=api_base, limits=_limits())
            clients[api_base] = client
            logger.debug("AI 异步客户端已创建并缓存 host=%s", api_base)
        return client


def close_ai_clients() -> None:
    """关闭全部同步池客户端（幂等；供 lifespan 与测试调用）。"""
    with _lock:
        clients = list(_sync_clients.values())
        _sync_clients.clear()
    for client in clients:
        try:
            client.close()
        except Exception:  # noqa: BLE001 — 关闭失败不影响退出流程
            logger.warning("关闭同步模型客户端失败", exc_info=True)


async def aclose_ai_clients() -> None:
    """关闭同步与异步池客户端（幂等；供 lifespan 关闭阶段调用）。"""
    close_ai_clients()
    with _lock:
        pending: list[httpx.AsyncClient] = []
        for clients in list(_async_pools.values()):
            pending.extend(clients.values())
        _async_pools.clear()
    for client in pending:
        try:
            await client.aclose()
        except Exception:  # noqa: BLE001
            logger.warning("关闭异步模型客户端失败", exc_info=True)


def stats() -> dict[str, int]:
    """池化状态（供测试与指标端点观察）。"""
    with _lock:
        return {
            "sync_clients": len(_sync_clients),
            "async_loops": len(_async_pools),
            "async_clients": sum(len(clients) for clients in _async_pools.values()),
        }
