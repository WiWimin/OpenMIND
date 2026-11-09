from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.config import get_settings
from app.core.exceptions import AppError, error_body
from app.utils.storage import ensure_content_length


class UploadGuardMiddleware(BaseHTTPMiddleware):
    """上传预检中间件：在 FastAPI 解析 multipart body 之前用 Content-Length 拦截超大请求。

    FastAPI 会先 `await request.form()` 再解析依赖，因此仅靠依赖无法避免读取超大 body。
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.method in ("POST", "PUT", "PATCH"):
            content_type = request.headers.get("content-type", "")
            if content_type.startswith("multipart/form-data"):
                try:
                    ensure_content_length(
                        request.headers.get("content-length"),
                        max_mb=get_settings().max_upload_mb,
                    )
                except AppError as exc:
                    return JSONResponse(
                        status_code=exc.http_status,
                        content=error_body(
                            exc.error_code, exc.message, exc.retryable, exc.details
                        ),
                    )
        return await call_next(request)
