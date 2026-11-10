"""异步任务执行器（ADR-3）：独立会话运行任务体，统一状态流转与异常归一。"""

from __future__ import annotations

import logging
from collections.abc import Callable

from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.db.session import SessionLocal
from app.repositories import job_repository
from app.services import job_service

logger = logging.getLogger(__name__)

# 测试可通过替换该工厂，把后台任务接到测试内存库（见 tests/conftest.py）
session_factory: Callable[[], Session] = SessionLocal

# 任务体：接收（独立会话, 进度回调），失败以 AppError 上抛（错误码/文案写入任务）
JobFn = Callable[[Session, Callable[[int], None]], None]


def run_job(job_id: str, fn: JobFn) -> None:
    """执行任务：`pending → running → succeeded | failed`。

    使用独立会话（不复用请求 Session）；`AppError` 记录其错误码与文案，
    未知异常记 `INTERNAL_ERROR`，均不让异常逃逸到响应链路。
    """
    db = session_factory()
    job = None
    try:
        job = job_repository.get(db, job_id)
        if job is None:
            logger.error("任务不存在，跳过执行 job_id=%s", job_id)
            return
        if job.status != job_service.PENDING:
            logger.warning(
                "任务状态非 pending，跳过执行 job_id=%s status=%s", job_id, job.status
            )
            return
        job_service.mark_running(db, job)

        def _progress(value: int) -> None:
            job_service.update_progress(db, job, value)

        fn(db, _progress)
        job_service.mark_succeeded(db, job)
    except AppError as exc:
        _fail_safely(db, job, exc.error_code, exc.message)
    except Exception:
        logger.exception("异步任务异常 job_id=%s", job_id)
        _fail_safely(db, job, "INTERNAL_ERROR", "任务执行失败")
    finally:
        db.close()


def _fail_safely(
    db: Session, job: object, error_code: str, error_message: str
) -> None:
    if job is None:
        return
    try:
        db.rollback()
        job_service.mark_failed(db, job, error_code, error_message)  # type: ignore[arg-type]
    except Exception:  # noqa: BLE001 — 状态写入失败只告警
        logger.exception("任务失败状态写入异常 job_id=%s", getattr(job, "job_id", "?"))
