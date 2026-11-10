from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, File, Form, Response, UploadFile, status

from app.api.deps import CurrentUser, DbSession, UploadSizeCheck
from app.api.page import PageParams, list_envelope
from app.core.config import get_settings
from app.schemas.common import Envelope, ListData, MaterialDeleteResult
from app.schemas.job import JobAccepted, JobRead
from app.schemas.material import MaterialRead
from app.services import job_service, job_tasks, material_service

router = APIRouter(tags=["materials"])

# 异步受理：202 + 任务对象；关闭 ASYNC_JOBS_ENABLED 时走原同步逻辑
_ACCEPTED = status.HTTP_202_ACCEPTED


@router.post(
    "/meetings/{meeting_id}/materials",
    status_code=status.HTTP_201_CREATED,
    response_model=Envelope[MaterialRead] | Envelope[JobAccepted],
)
async def upload_material(
    meeting_id: str,
    db: DbSession,
    current_user: CurrentUser,
    _size_check: UploadSizeCheck,
    background_tasks: BackgroundTasks,
    response: Response,
    file: Annotated[UploadFile, File()],
    source: Annotated[str | None, Form()] = None,
    material_type: Annotated[str | None, Form()] = None,
) -> Envelope[MaterialRead] | Envelope[JobAccepted]:
    content = await file.read()
    if get_settings().async_jobs_enabled:
        material = material_service.upload_material(
            db,
            meeting_id=meeting_id,
            user_id=current_user.user_id,
            file_name=file.filename or "upload",
            content=content,
            source=source,
            material_type=material_type,
            defer_processing=True,
        )
        job = job_service.enqueue(
            db,
            background_tasks,
            user_id=current_user.user_id,
            job_type="material_parse",
            resource_type="material",
            resource_id=material.material_id,
            fn=job_tasks.material_parse(material.material_id, current_user.user_id),
        )
        response.status_code = _ACCEPTED
        return Envelope(data=JobAccepted(job=JobRead.model_validate(job)))
    material = material_service.upload_material(
        db,
        meeting_id=meeting_id,
        user_id=current_user.user_id,
        file_name=file.filename or "upload",
        content=content,
        source=source,
        material_type=material_type,
    )
    return Envelope(data=MaterialRead.model_validate(material))


@router.get(
    "/meetings/{meeting_id}/materials",
    response_model=Envelope[ListData[MaterialRead]],
)
def list_materials(
    meeting_id: str,
    db: DbSession,
    current_user: CurrentUser,
    params: PageParams,
) -> Envelope[ListData[MaterialRead]]:
    items, total = material_service.list_materials(
        db,
        meeting_id=meeting_id,
        user_id=current_user.user_id,
        page=params.page,
        page_size=params.page_size,
    )
    return list_envelope(
        items, MaterialRead, page=params.page, page_size=params.page_size, total=total
    )


@router.get("/materials/{material_id}", response_model=Envelope[MaterialRead])
def get_material(
    material_id: str, db: DbSession, current_user: CurrentUser
) -> Envelope[MaterialRead]:
    material = material_service.get_owned_material(db, material_id, current_user.user_id)
    return Envelope(data=MaterialRead.model_validate(material))


@router.delete("/materials/{material_id}", response_model=Envelope[MaterialDeleteResult])
def delete_material(
    material_id: str, db: DbSession, current_user: CurrentUser
) -> Envelope[MaterialDeleteResult]:
    material_service.delete_material(db, material_id, current_user.user_id)
    return Envelope(data=MaterialDeleteResult(material_id=material_id))


@router.post(
    "/materials/{material_id}/retry",
    response_model=Envelope[MaterialRead] | Envelope[JobAccepted],
)
def retry_material(
    material_id: str,
    db: DbSession,
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
    response: Response,
) -> Envelope[MaterialRead] | Envelope[JobAccepted]:
    """重新解析/索引处理失败的材料：仅 `failed` 可重试，成功转 `processed`。"""
    if get_settings().async_jobs_enabled:
        material = material_service.retry_material(
            db, material_id, current_user.user_id, defer_processing=True
        )
        job = job_service.enqueue(
            db,
            background_tasks,
            user_id=current_user.user_id,
            job_type="material_parse",
            resource_type="material",
            resource_id=material.material_id,
            fn=job_tasks.material_parse(material.material_id, current_user.user_id),
        )
        response.status_code = _ACCEPTED
        return Envelope(data=JobAccepted(job=JobRead.model_validate(job)))
    material = material_service.retry_material(
        db, material_id, current_user.user_id
    )
    return Envelope(data=MaterialRead.model_validate(material))
