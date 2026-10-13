from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.common import Envelope, ListData, MeetingDeleteResult
from app.schemas.meeting import (
    MeetingCreate,
    MeetingRead,
    MeetingStatus,
    MeetingUpdate,
)
from app.services import meeting_service
from app.utils.pagination import build_pagination

router = APIRouter(prefix="/meetings", tags=["meetings"])


@router.get("", response_model=Envelope[ListData[MeetingRead]])
def list_meetings(
    db: DbSession,
    current_user: CurrentUser,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    meeting_status: Annotated[MeetingStatus | None, Query(alias="status")] = None,
) -> Envelope[ListData[MeetingRead]]:
    items, total = meeting_service.list_meetings(
        db,
        current_user.user_id,
        status=meeting_status.value if meeting_status else None,
        page=page,
        page_size=page_size,
    )
    data = ListData[MeetingRead](
        items=[MeetingRead.model_validate(item) for item in items],
        pagination=build_pagination(page, page_size, total),
    )
    return Envelope(data=data)


@router.post("", status_code=status.HTTP_201_CREATED, response_model=Envelope[MeetingRead])
def create_meeting(
    payload: MeetingCreate, db: DbSession, current_user: CurrentUser
) -> Envelope[MeetingRead]:
    meeting = meeting_service.create_meeting(db, current_user.user_id, payload)
    return Envelope(data=MeetingRead.model_validate(meeting))


@router.get("/{meeting_id}", response_model=Envelope[MeetingRead])
def get_meeting(
    meeting_id: str, db: DbSession, current_user: CurrentUser
) -> Envelope[MeetingRead]:
    meeting = meeting_service.get_owned_meeting(db, meeting_id, current_user.user_id)
    return Envelope(data=MeetingRead.model_validate(meeting))


@router.patch("/{meeting_id}", response_model=Envelope[MeetingRead])
def update_meeting(
    meeting_id: str, payload: MeetingUpdate, db: DbSession, current_user: CurrentUser
) -> Envelope[MeetingRead]:
    meeting = meeting_service.update_meeting(db, meeting_id, current_user.user_id, payload)
    return Envelope(data=MeetingRead.model_validate(meeting))


@router.delete("/{meeting_id}", response_model=Envelope[MeetingDeleteResult])
def delete_meeting(
    meeting_id: str, db: DbSession, current_user: CurrentUser
) -> Envelope[MeetingDeleteResult]:
    meeting_service.delete_meeting(db, meeting_id, current_user.user_id)
    return Envelope(data=MeetingDeleteResult(meeting_id=meeting_id))


@router.post("/{meeting_id}/archive", response_model=Envelope[MeetingRead])
def archive_meeting(
    meeting_id: str, db: DbSession, current_user: CurrentUser
) -> Envelope[MeetingRead]:
    meeting = meeting_service.archive_meeting(db, meeting_id, current_user.user_id)
    return Envelope(data=MeetingRead.model_validate(meeting))
