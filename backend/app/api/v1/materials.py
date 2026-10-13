from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, Form, Query, UploadFile, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.common import Envelope, ListData, MaterialDeleteResult
from app.schemas.material import MaterialRead
from app.services import material_service
from app.utils.pagination import build_pagination

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
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> Envelope[ListData[MaterialRead]]:
    items, total = material_service.list_materials(
        db,
        meeting_id=meeting_id,
        user_id=current_user.user_id,
        page=page,
        page_size=page_size,
    )
    data = ListData[MaterialRead](
        items=[MaterialRead.model_validate(item) for item in items],
        pagination=build_pagination(page, page_size, total),
    )
    return Envelope(data=data)


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
