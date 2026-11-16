"""异步任务业务规则（ADR-3）：创建、归属校验、状态流转与僵尸任务回收。"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import resource_not_found
from app.models.async_job import AsyncJob
from app.repositories import job_repository
from app.services import task_runner
from app.utils.ids import new_id
from app.utils.pagination import paginate_by

logger = logging.getLogger(__name__)

# 状态机：pending → running → succeeded | failed（终态不可再变）
PENDING = "pending"
RUNNING = "running"
SUCCEEDED = "succeeded"
FAILED = "failed"


def create_job(
    db: Session,
    *,
    user_id: str,
    job_type: str,
    resource_type: str,
    resource_id: str | None,
    payload: dict | None = None,
    priority: int = 0,
) -> AsyncJob:
    settings = get_settings()
    return job_repository.create(
        db,
        job_id=new_id("job"),
        user_id=user_id,
        job_type=job_type,
        resource_type=resource_type,
        resource_id=resource_id,
        payload=payload,
        max_attempts=max(1, settings.job_max_attempts),
        priority=priority,
        next_run_at=datetime.now(UTC),
    )


def enqueue(
    db: Session,
    background_tasks: BackgroundTasks | None,
    *,
    user_id: str,
    job_type: str,
    resource_type: str,
    resource_id: str | None,
    fn: Callable[[Session, Callable[[int], None]], None] | None = None,
    payload: dict | None = None,
    priority: int = 0,
) -> AsyncJob:
    """创建任务。

    - `JOB_WORKER_ENABLED=true`：只落库，由独立 worker 认领执行（持久化队列）；
    - 否则注册到 `BackgroundTasks`（旧行为，响应返回后执行）。
    """
    job = create_job(
        db,
        user_id=user_id,
        job_type=job_type,
        resource_type=resource_type,
        resource_id=resource_id,
        payload=payload,
        priority=priority,
    )
    if not get_settings().job_worker_enabled and background_tasks is not None and fn is not None:
        background_tasks.add_task(task_runner.run_job, job.job_id, fn)
    return job


def get_owned_job(db: Session, job_id: str, user_id: str) -> AsyncJob:
    job = job_repository.get_owned(db, job_id, user_id)
    if job is None:
        raise resource_not_found("任务")
    return job


def list_jobs(
    db: Session,
    *,
    user_id: str,
    resource_type: str | None = None,
    resource_id: str | None = None,
    page: int,
    page_size: int,
) -> tuple[list[AsyncJob], int]:
    return paginate_by(
        job_repository.list_by_user,
        job_repository.count_by_user,
        db,
        user_id,
        resource_type=resource_type,
        resource_id=resource_id,
        page=page,
        page_size=page_size,
    )


def mark_running(db: Session, job: AsyncJob) -> None:
    job_repository.set_status(
        db, job, status=RUNNING, started_at=datetime.now(UTC)
    )


def update_progress(db: Session, job: AsyncJob, value: int) -> None:
    # 短事务：进度独立提交，写入失败只告警，不阻断任务主流程
    try:
        job_repository.set_progress(db, job, max(0, min(100, value)))
    except Exception:  # noqa: BLE001
        db.rollback()
        logger.warning("任务进度写入失败 job_id=%s progress=%s", job.job_id, value)


def mark_succeeded(db: Session, job: AsyncJob) -> None:
    job_repository.set_status(
        db,
        job,
        status=SUCCEEDED,
        progress=100,
        finished_at=datetime.now(UTC),
    )


def mark_failed(
    db: Session, job: AsyncJob, error_code: str, error_message: str
) -> None:
    job_repository.set_status(
        db,
        job,
        status=FAILED,
        error_code=error_code,
        error_message=error_message,
        finished_at=datetime.now(UTC),
    )


def claim_next(db: Session, worker_id: str) -> AsyncJob | None:
    """worker 认领一个到期任务（`pending → running`）。"""
    return job_repository.claim_next(db, worker_id=worker_id, now=datetime.now(UTC))


def heartbeat(db: Session, job: AsyncJob) -> None:
    job_repository.heartbeat(db, job, now=datetime.now(UTC))


def retry_or_fail(
    db: Session, job: AsyncJob, error_code: str, error_message: str
) -> bool:
    """可重试错误回到 pending（指数退避），否则落 failed；返回是否重试。"""
    from app.agent.workflow import DEFAULT_RETRY_CODES

    attempts = job.attempts or 0
    if error_code in DEFAULT_RETRY_CODES and attempts < (job.max_attempts or 1):
        delay = min(60.0, 2.0 ** max(0, attempts - 1) * 5.0)
        job_repository.release_for_retry(
            db, job, next_run_at=datetime.now(UTC) + timedelta(seconds=delay)
        )
        logger.warning(
            "任务失败可重试 job_id=%s code=%s attempt=%s/%s",
            job.job_id,
            error_code,
            attempts,
            job.max_attempts,
        )
        return True
    mark_failed(db, job, error_code, error_message)
    return False


def reap_stale(db: Session, *, older_than_minutes: int | None = None) -> int:
    """回收僵尸任务：pending 超窗（进程重启丢失）或 running 超时 → failed JOB_TIMEOUT。"""
    minutes = (
        get_settings().async_job_stale_minutes
        if older_than_minutes is None
        else older_than_minutes
    )
    now = datetime.now(UTC)
    cutoff = now - timedelta(minutes=minutes)
    return job_repository.reap(
        db, pending_cutoff=cutoff, running_cutoff=cutoff, finished_at=now
    )


def reap_stale_on_startup() -> None:
    """启动时兜底回收上次进程残留的任务；失败只告警，不阻断启动。"""
    db = task_runner.session_factory()
    try:
        count = reap_stale(db)
        if count:
            logger.warning("启动回收超时任务 count=%s", count)
    except Exception:  # noqa: BLE001 — 启动探活失败不应阻止服务启动
        logger.exception("启动回收超时任务失败（忽略，读取时仍会懒回收）")
    finally:
        db.close()


def get_job_with_lazy_reap(db: Session, job_id: str, user_id: str) -> AsyncJob:
    """读取任务；发现超时的 pending/running 时懒回收为 failed（兜底启动回收遗漏）。"""
    job = get_owned_job(db, job_id, user_id)
    if job.status in (PENDING, RUNNING):
        reference = job.started_at or job.created_at
        if reference is not None:
            if reference.tzinfo is None:
                reference = reference.replace(tzinfo=UTC)
            age = datetime.now(UTC) - reference
            if age > timedelta(minutes=get_settings().async_job_stale_minutes):
                mark_failed(db, job, "JOB_TIMEOUT", "任务处理超时")
    return job
