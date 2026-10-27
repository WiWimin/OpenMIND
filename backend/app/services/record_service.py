from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.models.record import MeetingRecord
from app.repositories import (
    action_item_repository,
    issue_repository,
    record_repository,
)
from app.schemas.record import RecordCreate, RecordUpdate
from app.services import meeting_service
from app.utils.ids import new_id


def _not_found() -> AppError:
    return AppError("RESOURCE_NOT_FOUND", "记录不存在或不可访问", http_status=404)


def create_record(
    db: Session, *, meeting_id: str, user_id: str, payload: RecordCreate
) -> MeetingRecord:
    meeting_service.get_mutable_meeting(db, meeting_id, user_id)
    return record_repository.create(
        db,
        record_id=new_id("rec"),
        meeting_id=meeting_id,
        content=payload.content,
        record_type=payload.record_type.value,
        marker_type=payload.marker_type.value if payload.marker_type else None,
    )


def list_records(
    db: Session, *, meeting_id: str, user_id: str, page: int, page_size: int
) -> tuple[list[MeetingRecord], int]:
    meeting_service.get_owned_meeting(db, meeting_id, user_id)
    offset = (page - 1) * page_size
    items = record_repository.list_by_meeting(db, meeting_id, limit=page_size, offset=offset)
    total = record_repository.count_by_meeting(db, meeting_id)
    return items, total


def get_owned_record(db: Session, record_id: str, user_id: str) -> MeetingRecord:
    record = record_repository.get_owned(db, record_id, user_id)
    if record is None:
        raise _not_found()
    return record


def update_record(
    db: Session, record_id: str, user_id: str, payload: RecordUpdate
) -> MeetingRecord:
    record = get_owned_record(db, record_id, user_id)
    meeting_service.get_mutable_meeting(db, record.meeting_id, user_id)
    data = payload.model_dump(exclude_unset=True)
    if "content" in data and data["content"] is not None:
        record.content = data["content"]
    if "marker_type" in data:
        marker = data["marker_type"]
        record.marker_type = marker.value if marker else None
    return record_repository.update(db, record)


def delete_record(db: Session, record_id: str, user_id: str) -> None:
    record = get_owned_record(db, record_id, user_id)
    meeting_service.get_mutable_meeting(db, record.meeting_id, user_id)
    if action_item_repository.exists_by_source_record(
        db, record_id
    ) or issue_repository.exists_by_source_record(db, record_id):
        raise AppError(
            "BUSINESS_RULE_VIOLATION",
            "记录被行动项或问题引用，无法删除",
            http_status=409,
        )
    record_repository.delete(db, record)
