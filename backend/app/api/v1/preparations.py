from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DbSession
from app.schemas.common import Envelope, ListData
from app.schemas.preparation import (
    PreparationGenerateRequest,
    PreparationRead,
    PreparationUpdate,
)
from app.services import preparation_service
from app.utils.pagination import build_pagination

router = APIRouter(tags=["preparations"])


@router.post(
    "/meetings/{meeting_id}/prepare",
    response_model=Envelope[PreparationRead],
)
def generate_preparation(
    meeting_id: str,
    payload: PreparationGenerateRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> Envelope[PreparationRead]:
    preparation = preparation_service.generate_preparation(
        db,
        meeting_id=meeting_id,
        user_id=current_user.user_id,
        user_goal=payload.user_goal,
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
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> Envelope[ListData[PreparationRead]]:
    items, total = preparation_service.list_preparations(
        db,
        meeting_id=meeting_id,
        user_id=current_user.user_id,
        page=page,
        page_size=page_size,
    )
    data = ListData[PreparationRead](
        items=[PreparationRead.model_validate(item) for item in items],
        pagination=build_pagination(page, page_size, total),
    )
    return Envelope(data=data)


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
