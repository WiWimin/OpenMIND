from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.common import Envelope, ListData, RecordDeleteResult
from app.schemas.record import MeetingRecordRead, RecordCreate, RecordUpdate
from app.services import record_service
from app.utils.pagination import build_pagination

router = APIRouter(tags=["records"])


@router.post(
    "/meetings/{meeting_id}/records",
    status_code=status.HTTP_201_CREATED,
    response_model=Envelope[MeetingRecordRead],
)
def create_record(
    meeting_id: str,
    payload: RecordCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> Envelope[MeetingRecordRead]:
    record = record_service.create_record(
        db, meeting_id=meeting_id, user_id=current_user.user_id, payload=payload
    )
    return Envelope(data=MeetingRecordRead.model_validate(record))


@router.get(
    "/meetings/{meeting_id}/records",
    response_model=Envelope[ListData[MeetingRecordRead]],
)
def list_records(
    meeting_id: str,
    db: DbSession,
    current_user: CurrentUser,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> Envelope[ListData[MeetingRecordRead]]:
    items, total = record_service.list_records(
        db,
        meeting_id=meeting_id,
        user_id=current_user.user_id,
        page=page,
        page_size=page_size,
    )
    data = ListData[MeetingRecordRead](
        items=[MeetingRecordRead.model_validate(item) for item in items],
        pagination=build_pagination(page, page_size, total),
    )
    return Envelope(data=data)


@router.patch("/records/{record_id}", response_model=Envelope[MeetingRecordRead])
def update_record(
    record_id: str,
    payload: RecordUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> Envelope[MeetingRecordRead]:
    record = record_service.update_record(db, record_id, current_user.user_id, payload)
    return Envelope(data=MeetingRecordRead.model_validate(record))


@router.delete("/records/{record_id}", response_model=Envelope[RecordDeleteResult])
def delete_record(
    record_id: str, db: DbSession, current_user: CurrentUser
) -> Envelope[RecordDeleteResult]:
    record_service.delete_record(db, record_id, current_user.user_id)
    return Envelope(data=RecordDeleteResult(record_id=record_id))
