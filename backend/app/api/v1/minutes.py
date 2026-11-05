from __future__ import annotations

from fastapi import APIRouter, status

from app.api.deps import CurrentUser, DbSession
from app.api.page import PageParams, list_envelope
from app.schemas.common import Envelope, ListData
from app.schemas.minutes import MinutesGenerateRequest, MinutesRead, MinutesUpdate
from app.services import minutes_service

router = APIRouter(tags=["minutes"])


@router.post(
    "/meetings/{meeting_id}/minutes/generate",
    status_code=status.HTTP_201_CREATED,
    response_model=Envelope[MinutesRead],
)
def generate_minutes(
    meeting_id: str,
    payload: MinutesGenerateRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> Envelope[MinutesRead]:
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
