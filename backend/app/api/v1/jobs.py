from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DbSession
from app.api.page import PageParams, list_envelope
from app.schemas.common import Envelope, ListData
from app.schemas.job import JobRead
from app.services import job_service

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=Envelope[JobRead])
def get_job(
    job_id: str, db: DbSession, current_user: CurrentUser
) -> Envelope[JobRead]:
    """任务详情（仅本人）；超时的 pending/running 读取时懒回收为 failed。"""
    job = job_service.get_job_with_lazy_reap(db, job_id, current_user.user_id)
    return Envelope(data=JobRead.model_validate(job))


@router.get("", response_model=Envelope[ListData[JobRead]])
def list_jobs(
    db: DbSession,
    current_user: CurrentUser,
    params: PageParams,
    resource_type: Annotated[str | None, Query(max_length=40)] = None,
    resource_id: Annotated[str | None, Query(max_length=40)] = None,
) -> Envelope[ListData[JobRead]]:
    """任务分页列表（仅本人），可按关联资源过滤。"""
    items, total = job_service.list_jobs(
        db,
        user_id=current_user.user_id,
        resource_type=resource_type,
        resource_id=resource_id,
        page=params.page,
        page_size=params.page_size,
    )
    return list_envelope(
        items, JobRead, page=params.page, page_size=params.page_size, total=total
    )
