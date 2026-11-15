from __future__ import annotations

import mimetypes
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, File, Form, Response, UploadFile, status
from starlette.concurrency import run_in_threadpool

from app.api.deps import CurrentUser, DbSession, UploadSizeCheck
from app.api.page import PageParams, list_envelope
from app.core.config import get_settings
from app.schemas.common import Envelope, ListData, MaterialDeleteResult
from app.schemas.job import JobAccepted, JobRead
from app.schemas.material import MaterialRead
from app.services import job_service, job_tasks, material_service

router = APIRouter(tags=["materials"])


def _read_with_size(material) -> MaterialRead:
    """读模型 + 原始文件大小（stat 计算，非数据库列），供本地同步估算下载量。"""
    return MaterialRead.model_validate(material).model_copy(
        update={"file_size": material_service.file_size_of(material)}
    )

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
    client_op_id: Annotated[str | None, Form(max_length=64)] = None,
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
            client_op_id=client_op_id,
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
    material = await run_in_threadpool(
        material_service.upload_material,
        db,
        meeting_id=meeting_id,
        user_id=current_user.user_id,
        file_name=file.filename or "upload",
        content=content,
        source=source,
        material_type=material_type,
        client_op_id=client_op_id,
    )
    return Envelope(data=_read_with_size(material))


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
        [_read_with_size(item) for item in items],
        MaterialRead,
        page=params.page,
        page_size=params.page_size,
        total=total,
    )


@router.get("/materials/{material_id}", response_model=Envelope[MaterialRead])
def get_material(
    material_id: str, db: DbSession, current_user: CurrentUser
) -> Envelope[MaterialRead]:
    material = material_service.get_owned_material(db, material_id, current_user.user_id)
    return Envelope(data=_read_with_size(material))


@router.get("/materials/{material_id}/download")
def download_material(
    material_id: str, db: DbSession, current_user: CurrentUser
) -> Response:
    """下载材料原始文件（本地工作区同步用）。

    只接受 material_id，不接受任何路径；归属校验后读取服务端存储内容。
    """
    material = material_service.get_owned_material(db, material_id, current_user.user_id)
    content = material_service.read_material_file(material)
    media_type = mimetypes.guess_type(material.file_name)[0] or "application/octet-stream"
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(material.file_name)}"
        },
    )


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
            payload={"material_id": material.material_id},
        )
        response.status_code = _ACCEPTED
        return Envelope(data=JobAccepted(job=JobRead.model_validate(job)))
    material = material_service.retry_material(
        db, material_id, current_user.user_id
    )
    return Envelope(data=_read_with_size(material))
