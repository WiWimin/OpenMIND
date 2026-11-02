from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, Form, UploadFile, status

from app.api.deps import CurrentUser, DbSession
from app.api.page import PageParams, list_envelope
from app.schemas.common import Envelope, ListData, MaterialDeleteResult
from app.schemas.material import MaterialRead
from app.services import material_service

router = APIRouter(tags=["materials"])


@router.post(
    "/meetings/{meeting_id}/materials",
    status_code=status.HTTP_201_CREATED,
    response_model=Envelope[MaterialRead],
)
async def upload_material(
    meeting_id: str,
    db: DbSession,
    current_user: CurrentUser,
    file: Annotated[UploadFile, File()],
    source: Annotated[str | None, Form()] = None,
    material_type: Annotated[str | None, Form()] = None,
) -> Envelope[MaterialRead]:
    content = await file.read()
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
