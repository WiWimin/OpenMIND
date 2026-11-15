from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.ai.connection import aclose_ai_clients
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.error_middleware import CatchAllErrorMiddleware
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging
from app.core.rate_limit import RateLimitMiddleware
from app.core.startup_check import log_migration_status
from app.core.upload_guard import UploadGuardMiddleware
from app.services import ai_audit_service, job_service


def create_app() -> FastAPI:
    configure_logging()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        # 启动兜底：回收上次进程残留的 pending/running 任务（失败不阻断启动）
        job_service.reap_stale_on_startup()
        # 启动兜底：回收未收尾的 running 审计行（失败不阻断启动）
        ai_audit_service.reap_stale_on_startup()
        # 启动兜底：核对 alembic_version 与代码 head（不一致只告警，不阻断）
        log_migration_status()
        try:
            yield
        finally:
            # 关闭池化的模型 HTTP 客户端（同步 + 异步），释放 keep-alive 连接
            await aclose_ai_clients()

    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

    # 注册顺序 = 由内到外（Starlette 后注册者在最外层）：
    #   UploadGuard → RateLimit → CatchAll → CORS（最外层）
    # `CatchAllErrorMiddleware` 必须位于 CORS 内侧：未捕获异常由最外层
    # ServerErrorMiddleware 生成 500，该响应不经过 CORS，浏览器会把服务端
    # 故障误报为「Network Error」（见 app/core/error_middleware.py）。
    app.add_middleware(UploadGuardMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(CatchAllErrorMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    @app.get("/health", tags=["health"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
