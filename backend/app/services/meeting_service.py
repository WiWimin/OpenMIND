from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import AppError, resource_not_found
from app.models.meeting import Meeting
from app.models.user import utc_now
from app.repositories import (
    action_item_repository,
    audio_repository,
    chunk_repository,
    issue_repository,
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
from app.utils.pagination import paginate_by

_ARCHIVED = "archived"


def get_owned_meeting(db: Session, meeting_id: str, user_id: str) -> Meeting:
    meeting = meeting_repository.get_owned(db, meeting_id, user_id)
    if meeting is None:
        raise resource_not_found("会议")
    return meeting


def get_mutable_meeting(db: Session, meeting_id: str, user_id: str) -> Meeting:
    meeting = get_owned_meeting(db, meeting_id, user_id)
    if meeting.status == _ARCHIVED:
        raise AppError(
            "BUSINESS_RULE_VIOLATION",
            "会议已归档，仅可查看",
            http_status=409,
        )
    return meeting


def list_meetings(
    db: Session,
    user_id: str,
    *,
    status: str | None,
    page: int,
    page_size: int,
) -> tuple[list[Meeting], int]:
    return paginate_by(
        meeting_repository.list_by_user,
        meeting_repository.count_by_user,
        db,
        user_id,
        page=page,
        page_size=page_size,
        status=status,
    )


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
    meeting = get_mutable_meeting(db, meeting_id, user_id)
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

    # 音频必须先于记录删除（audio.record_id 引用 meeting_records）；
    # 同时清理主文件与实时会话的分片目录。
    for audio in audio_repository.list_all_by_meeting(db, meeting_id):
        storage.delete_object(settings.storage_dir, audio.storage_key)
        for segment in audio.segments or []:
            seq = segment.get("seq")
            if seq is not None:
                storage.delete_object(
                    settings.storage_dir,
                    f"audio/{audio.audio_id}/chunks/{seq:04d}.{audio.type}",
                )
        storage.remove_tree(settings.storage_dir, f"audio/{audio.audio_id}")
    audio_repository.delete_by_meeting(db, meeting_id)

    action_item_repository.delete_by_meeting(db, meeting_id)
    minutes_repository.delete_by_meeting(db, meeting_id)
    preparation_repository.delete_by_meeting(db, meeting_id)
    record_repository.delete_by_meeting(db, meeting_id)
    issue_repository.delete_by_meeting(db, meeting_id)
    chunk_repository.delete_by_meeting(db, meeting_id)
    material_repository.delete_by_meeting(db, meeting_id)
    meeting_repository.delete(db, meeting)
