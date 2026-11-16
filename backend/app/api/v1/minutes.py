from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Response, status

from app.api.deps import CurrentUser, DbSession
from app.api.page import PageParams, list_envelope
from app.core.config import get_settings
from app.schemas.common import Envelope, ListData
from app.schemas.job import JobAccepted, JobRead
from app.schemas.minutes import MinutesGenerateRequest, MinutesRead, MinutesUpdate
from app.services import job_service, job_tasks, minutes_service

router = APIRouter(tags=["minutes"])

# 异步受理：202 + 任务对象；关闭 ASYNC_JOBS_ENABLED 时走原同步逻辑
_ACCEPTED = status.HTTP_202_ACCEPTED


@router.post(
    "/meetings/{meeting_id}/minutes/generate",
    status_code=status.HTTP_201_CREATED,
    response_model=Envelope[MinutesRead] | Envelope[JobAccepted],
)
def generate_minutes(
    meeting_id: str,
    payload: MinutesGenerateRequest,
    db: DbSession,
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
    response: Response,
) -> Envelope[MinutesRead] | Envelope[JobAccepted]:
    if get_settings().async_jobs_enabled:
        # 同步校验归属/记录/模型配置（404/400 先于受理返回），LLM 生成交后台任务
        minutes_service.prepare_minutes_context(
            db, meeting_id=meeting_id, user_id=current_user.user_id, payload=payload
        )
        job = job_service.enqueue(
            db,
            background_tasks,
            user_id=current_user.user_id,
            job_type="minutes_generate",
            resource_type="minutes",
            resource_id=None,
            fn=job_tasks.minutes_generate(
                meeting_id, current_user.user_id, payload
            ),
        )
        response.status_code = _ACCEPTED
        return Envelope(data=JobAccepted(job=JobRead.model_validate(job)))
    minutes = minutes_service.generate_minutes(
        db, meeting_id=meeting_id, user_id=current_user.user_id, payload=payload
    )
    return Envelope(data=MinutesRead.model_validate(minutes))


@router.get(
    "/meetings/{meeting_id}/minutes", response_model=Envelope[ListData[MinutesRead]]
)
def list_minutes(
    meeting_id: str,
    db: DbSession,
    current_user: CurrentUser,
    params: PageParams,
) -> Envelope[ListData[MinutesRead]]:
    items, total = minutes_service.list_minutes(
        db,
        meeting_id=meeting_id,
        user_id=current_user.user_id,
        page=params.page,
        page_size=params.page_size,
    )
    return list_envelope(
        items, MinutesRead, page=params.page, page_size=params.page_size, total=total
    )


@router.get("/minutes/{minutes_id}", response_model=Envelope[MinutesRead])
def get_minutes(
    minutes_id: str, db: DbSession, current_user: CurrentUser
) -> Envelope[MinutesRead]:
    minutes = minutes_service.get_owned_minutes(db, minutes_id, current_user.user_id)
    return Envelope(data=MinutesRead.model_validate(minutes))


@router.patch("/minutes/{minutes_id}", response_model=Envelope[MinutesRead])
def update_minutes(
    minutes_id: str,
    payload: MinutesUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> Envelope[MinutesRead]:
    minutes = minutes_service.update_minutes(db, minutes_id, current_user.user_id, payload)
    return Envelope(data=MinutesRead.model_validate(minutes))


@router.post("/minutes/{minutes_id}/confirm", response_model=Envelope[MinutesRead])
def confirm_minutes(
    minutes_id: str, db: DbSession, current_user: CurrentUser
) -> Envelope[MinutesRead]:
    minutes = minutes_service.confirm_minutes(db, minutes_id, current_user.user_id)
    return Envelope(data=MinutesRead.model_validate(minutes))
