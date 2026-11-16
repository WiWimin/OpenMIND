"""兜底错误中间件：把未捕获异常在 CORS **内侧**转换成统一 500 错误体。

问题：FastAPI 注册的 `Exception` 处理器由最外层 `ServerErrorMiddleware` 执行，
而 `ServerErrorMiddleware` 位于所有用户中间件（含 `CORSMiddleware`）之外，
其 500 响应不携带 CORS 头 —— 浏览器因此把它当作跨域失败，前端 axios 只能报
「Network Error」，掩盖真实的服务端故障。

做法：本中间件注册在 CORS 内侧、业务中间件外侧，捕获所有逃出应用的异常并
生成与 `app/core/exceptions.py` 一致的错误体，使 500 仍能带上 CORS 头。
若响应已经开始（SSE 流式等），不能追加第二个响应，只能继续上抛。
"""

from __future__ import annotations

import logging

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.exceptions import error_body

logger = logging.getLogger(__name__)


class CatchAllErrorMiddleware:
    """捕获未捕获异常并返回统一 500 错误体（必须位于 CORSMiddleware 内侧）。"""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        response_started = False

        async def _send(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, receive, _send)
        except Exception:  # noqa: BLE001 — 兜底中间件职责即兜底
            if response_started:
                # 已开始写出响应（SSE/文件流）：交给 ServerErrorMiddleware 记录
                raise
            logger.exception(
                "未捕获异常转为 500 响应 path=%s", scope.get("path", "")
            )
            response = JSONResponse(
                status_code=500,
                content=error_body(
                    "INTERNAL_ERROR", "未预期的服务端错误，请稍后重试", retryable=True
                ),
            )
            await response(scope, receive, _send)
