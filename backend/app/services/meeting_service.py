from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.models.meeting import Meeting
from app.models.user import utc_now
from app.repositories import (
    action_item_repository,
    material_repository,
    meeting_repository,
    minutes_repository,
    preparation_repository,
    record_repository,
    task_repository,
)
from app.schemas.meeting import MeetingCreate, MeetingUpdate
from app.utils import storage
from app.utils.ids import new_id

_ARCHIVED = "archived"


def _not_found() -> AppError:
    return AppError("RESOURCE_NOT_FOUND", "会议不存在或不可访问", http_status=404)


def get_owned_meeting(db: Session, meeting_id: str, user_id: str) -> Meeting:
    meeting = meeting_repository.get_owned(db, meeting_id, user_id)
    if meeting is None:
        raise _not_found()
    return meeting


def list_meetings(
    db: Session,
    user_id: str,
    *,
    status: str | None,
    page: int,
    page_size: int,
) -> tuple[list[Meeting], int]:
    offset = (page - 1) * page_size
    items = meeting_repository.list_by_user(
        db, user_id, status=status, limit=page_size, offset=offset
    )
    total = meeting_repository.count_by_user(db, user_id, status=status)
    return items, total


def create_meeting(db: Session, user_id: str, payload: MeetingCreate) -> Meeting:
    return meeting_repository.create(
        db,
        meeting_id=new_id("mtg"),
        user_id=user_id,
        title=payload.title,
        topic=payload.topic,
        meeting_time=payload.meeting_time,
    )


def update_meeting(
    db: Session, meeting_id: str, user_id: str, payload: MeetingUpdate
) -> Meeting:
    meeting = get_owned_meeting(db, meeting_id, user_id)
    if meeting.status == _ARCHIVED:
        raise AppError("BUSINESS_RULE_VIOLATION", "会议已归档，不可编辑", http_status=409)
    data = payload.model_dump(exclude_unset=True)
    if "title" in data and data["title"] is None:
        raise AppError("VALIDATION_ERROR", "标题不能为空", http_status=422)
    for field, value in data.items():
        setattr(meeting, field, value)
    return meeting_repository.update(db, meeting)


def archive_meeting(db: Session, meeting_id: str, user_id: str) -> Meeting:
    meeting = get_owned_meeting(db, meeting_id, user_id)
    if meeting.status != _ARCHIVED:
        meeting.status = _ARCHIVED
        meeting.archived_at = utc_now()
        meeting_repository.update(db, meeting)
    return meeting


def _ensure_deletable(db: Session, meeting_id: str) -> None:
    if action_item_repository.has_converted_by_meeting(
        db, meeting_id
    ) or task_repository.exists_by_meeting(db, meeting_id):
        raise AppError(
            "BUSINESS_RULE_VIOLATION",
            "会议存在已转换的行动项或个人任务，无法删除",
            http_status=409,
        )


def delete_meeting(db: Session, meeting_id: str, user_id: str) -> None:
    meeting = get_owned_meeting(db, meeting_id, user_id)
    _ensure_deletable(db, meeting_id)

    settings = get_settings()
    for material in material_repository.list_all_by_meeting(db, meeting_id):
        storage.delete_object(settings.storage_dir, material.storage_key)

    action_item_repository.delete_by_meeting(db, meeting_id)
    minutes_repository.delete_by_meeting(db, meeting_id)
    preparation_repository.delete_by_meeting(db, meeting_id)
    record_repository.delete_by_meeting(db, meeting_id)
    material_repository.delete_by_meeting(db, meeting_id)
    meeting_repository.delete(db, meeting)
