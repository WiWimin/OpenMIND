from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.models.async_job import AsyncJob


def create(
    db: Session,
    *,
    job_id: str,
    user_id: str,
    job_type: str,
    resource_type: str,
    resource_id: str | None,
) -> AsyncJob:
    job = AsyncJob(
        job_id=job_id,
        user_id=user_id,
        job_type=job_type,
        resource_type=resource_type,
        resource_id=resource_id,
        status="pending",
        progress=0,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def get(db: Session, job_id: str) -> AsyncJob | None:
    return db.execute(
        select(AsyncJob).where(AsyncJob.job_id == job_id)
    ).scalar_one_or_none()


def get_owned(db: Session, job_id: str, user_id: str) -> AsyncJob | None:
    return db.execute(
        select(AsyncJob).where(
            AsyncJob.job_id == job_id, AsyncJob.user_id == user_id
        )
    ).scalar_one_or_none()


def _filtered(
    user_id: str,
    resource_type: str | None,
    resource_id: str | None,
):
    statement = select(AsyncJob).where(AsyncJob.user_id == user_id)
    if resource_type:
        statement = statement.where(AsyncJob.resource_type == resource_type)
    if resource_id:
        statement = statement.where(AsyncJob.resource_id == resource_id)
    return statement


def list_by_user(
    db: Session,
    user_id: str,
    *,
    resource_type: str | None = None,
    resource_id: str | None = None,
    limit: int,
    offset: int,
) -> list[AsyncJob]:
    statement = _filtered(user_id, resource_type, resource_id)
    return list(
        db.execute(
            statement.order_by(AsyncJob.created_at.desc()).limit(limit).offset(offset)
        )
        .scalars()
        .all()
    )


def count_by_user(
    db: Session,
    user_id: str,
    *,
    resource_type: str | None = None,
    resource_id: str | None = None,
) -> int:
    statement = _filtered(user_id, resource_type, resource_id)
    count_statement = select(func.count()).select_from(statement.subquery())
    return int(db.execute(count_statement).scalar_one())


def set_status(
    db: Session,
    job: AsyncJob,
    *,
    status: str,
    started_at: datetime | None = None,
    finished_at: datetime | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
    progress: int | None = None,
) -> None:
    job.status = status
    if started_at is not None:
        job.started_at = started_at
    if finished_at is not None:
        job.finished_at = finished_at
    if error_code is not None:
        job.error_code = error_code
    if error_message is not None:
        job.error_message = error_message
    if progress is not None:
        job.progress = progress
    db.commit()
    db.refresh(job)


def set_progress(db: Session, job: AsyncJob, progress: int) -> None:
    job.progress = progress
    db.commit()


def reap(
    db: Session,
    *,
    pending_cutoff: datetime,
    running_cutoff: datetime,
    finished_at: datetime,
) -> int:
    """把超时的 pending（进程重启丢失）与 running（执行卡死）任务置为 failed，返回条数。"""
    statement = (
        update(AsyncJob)
        .where(
            (
                (AsyncJob.status == "pending")
                & (AsyncJob.created_at <= pending_cutoff)
            )
            | (
                (AsyncJob.status == "running")
                & (AsyncJob.started_at <= running_cutoff)
            )
        )
        .values(
            status="failed",
            error_code="JOB_TIMEOUT",
            error_message="任务处理超时",
            finished_at=finished_at,
        )
    )
    result = db.execute(statement)
    db.commit()
    return int(result.rowcount or 0)


def delete_by_user(db: Session, user_id: str) -> None:
    db.execute(delete(AsyncJob).where(AsyncJob.user_id == user_id))
