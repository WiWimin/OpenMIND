from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Response, status

from app.api.deps import CurrentUser, DbSession
from app.api.page import PageParams, list_envelope
from app.core.config import get_settings
from app.schemas.common import Envelope, ListData
from app.schemas.job import JobAccepted, JobRead
from app.schemas.preparation import (
    PreparationGenerateRequest,
    PreparationRead,
    PreparationUpdate,
)
from app.services import job_service, job_tasks, preparation_service

router = APIRouter(tags=["preparations"])

# 异步受理：202 + 任务对象（resource_id 为 generating 占位行）；关闭开关走同步逻辑
_ACCEPTED = status.HTTP_202_ACCEPTED


@router.post(
    "/meetings/{meeting_id}/prepare",
    response_model=Envelope[PreparationRead] | Envelope[JobAccepted],
)
def generate_preparation(
    meeting_id: str,
    payload: PreparationGenerateRequest,
    db: DbSession,
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
    response: Response,
) -> Envelope[PreparationRead] | Envelope[JobAccepted]:
    if get_settings().async_jobs_enabled:
        # 同步校验归属/模型配置，先落 `generating` 占位行，任务转 draft/failed
        preparation_service.prepare_generation_context(
            db,
            meeting_id=meeting_id,
            user_id=current_user.user_id,
            user_goal=payload.user_goal,
            include_history=payload.include_history,
            model=payload.model,
            template_id=payload.template_id,
        )
        placeholder = preparation_service.create_generating(db, meeting_id=meeting_id)
        job = job_service.enqueue(
            db,
            background_tasks,
            user_id=current_user.user_id,
            job_type="preparation_generate",
            resource_type="preparation",
            resource_id=placeholder.preparation_id,
            fn=job_tasks.preparation_generate(
                meeting_id,
                current_user.user_id,
                placeholder.preparation_id,
                user_goal=payload.user_goal,
                include_history=payload.include_history,
                model=payload.model,
                template_id=payload.template_id,
            ),
        )
        response.status_code = _ACCEPTED
        return Envelope(data=JobAccepted(job=JobRead.model_validate(job)))
    preparation = preparation_service.generate_preparation(
        db,
        meeting_id=meeting_id,
        user_id=current_user.user_id,
        user_goal=payload.user_goal,
        include_history=payload.include_history,
        model=payload.model,
        template_id=payload.template_id,
    )
    return Envelope(data=PreparationRead.model_validate(preparation))


@router.get(
    "/meetings/{meeting_id}/preparations",
    response_model=Envelope[ListData[PreparationRead]],
)
def list_preparations(
    meeting_id: str,
    db: DbSession,
    current_user: CurrentUser,
    params: PageParams,
) -> Envelope[ListData[PreparationRead]]:
    items, total = preparation_service.list_preparations(
        db,
        meeting_id=meeting_id,
        user_id=current_user.user_id,
        page=params.page,
        page_size=params.page_size,
    )
    return list_envelope(
        items, PreparationRead, page=params.page, page_size=params.page_size, total=total
    )


@router.get("/preparations/{preparation_id}", response_model=Envelope[PreparationRead])
def get_preparation(
    preparation_id: str, db: DbSession, current_user: CurrentUser
) -> Envelope[PreparationRead]:
    preparation = preparation_service.get_owned_preparation(
        db, preparation_id, current_user.user_id
    )
    return Envelope(data=PreparationRead.model_validate(preparation))


@router.patch("/preparations/{preparation_id}", response_model=Envelope[PreparationRead])
def update_preparation(
    preparation_id: str,
    payload: PreparationUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> Envelope[PreparationRead]:
    preparation = preparation_service.update_preparation(
        db, preparation_id, current_user.user_id, payload
    )
    return Envelope(data=PreparationRead.model_validate(preparation))


@router.post(
    "/preparations/{preparation_id}/confirm",
    response_model=Envelope[PreparationRead],
)
def confirm_preparation(
    preparation_id: str, db: DbSession, current_user: CurrentUser
) -> Envelope[PreparationRead]:
    preparation = preparation_service.confirm_preparation(
        db, preparation_id, current_user.user_id
    )
    return Envelope(data=PreparationRead.model_validate(preparation))
