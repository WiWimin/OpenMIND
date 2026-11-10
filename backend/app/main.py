from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.ai.connection import aclose_ai_clients
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging
from app.core.rate_limit import RateLimitMiddleware
from app.core.upload_guard import UploadGuardMiddleware
from app.services import job_service


def create_app() -> FastAPI:
    configure_logging()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        # 启动兜底：回收上次进程残留的 pending/running 任务（失败不阻断启动）
        job_service.reap_stale_on_startup()
        try:
            yield
        finally:
            # 关闭池化的模型 HTTP 客户端（同步 + 异步），释放 keep-alive 连接
            await aclose_ai_clients()

    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(UploadGuardMiddleware)

    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    @app.get("/health", tags=["health"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
