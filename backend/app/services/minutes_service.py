from __future__ import annotations

from sqlalchemy.orm import Session

from app.ai.minutes import MinutesService
from app.core.exceptions import AppError
from app.models.meeting import Meeting
from app.models.minutes import MeetingMinutes
from app.repositories import minutes_repository, record_repository
from app.schemas.minutes import MinutesGenerateRequest, MinutesUpdate
from app.services import meeting_service
from app.services.model_config_service import (
    ModelConfig,
    build_llm_client,
    resolve_model_config,
)
from app.utils.ids import new_id

_STATUS_DRAFT = "draft"
_STATUS_CONFIRMED = "confirmed"
_MAX_RECORDS = 100


def generate_text(
    meeting: Meeting, transcripts: list[str], config: ModelConfig
) -> str:
    topic_parts = [meeting.title]
    if meeting.topic:
        topic_parts.append(meeting.topic)
    return MinutesService(build_llm_client(config)).generate(
        " / ".join(topic_parts), transcripts
    )


def _not_found() -> AppError:
    return AppError("RESOURCE_NOT_FOUND", "纪要不存在或不可访问", http_status=404)


def _gather(db: Session, meeting_id: str, record_ids: list[str]) -> tuple[list[str], list[str]]:
    if record_ids:
        records = record_repository.list_by_ids(db, meeting_id, record_ids)
    else:
        records = record_repository.list_by_meeting(
            db, meeting_id, limit=_MAX_RECORDS, offset=0
        )
    return [record.content for record in records], [record.record_id for record in records]


def generate_minutes(
    db: Session, *, meeting_id: str, user_id: str, payload: MinutesGenerateRequest
) -> MeetingMinutes:
    meeting = meeting_service.get_owned_meeting(db, meeting_id, user_id)
    transcripts, record_ids = _gather(db, meeting_id, payload.record_ids)
    config = resolve_model_config(db, user_id)
    content = generate_text(meeting, transcripts, config)
    minutes = minutes_repository.create(
        db,
        minutes_id=new_id("min"),
        meeting_id=meeting_id,
        content=content,
        source_record_ids=record_ids,
        status=_STATUS_DRAFT,
    )
    if payload.include_action_items:
        from app.services import action_item_service

        action_item_service.extract_action_items(
            db, meeting_id=meeting_id, user_id=user_id, record_ids=record_ids
        )
    return minutes


def list_minutes(
    db: Session, *, meeting_id: str, user_id: str, page: int, page_size: int
) -> tuple[list[MeetingMinutes], int]:
    meeting_service.get_owned_meeting(db, meeting_id, user_id)
    offset = (page - 1) * page_size
    items = minutes_repository.list_by_meeting(db, meeting_id, limit=page_size, offset=offset)
    total = minutes_repository.count_by_meeting(db, meeting_id)
    return items, total


def get_owned_minutes(db: Session, minutes_id: str, user_id: str) -> MeetingMinutes:
    minutes = minutes_repository.get_owned(db, minutes_id, user_id)
    if minutes is None:
        raise _not_found()
    return minutes


def update_minutes(
    db: Session, minutes_id: str, user_id: str, payload: MinutesUpdate
) -> MeetingMinutes:
    minutes = get_owned_minutes(db, minutes_id, user_id)
    data = payload.model_dump(exclude_unset=True)
    if data.get("content") is not None:
        minutes.content = data["content"]
    minutes.version += 1
    return minutes_repository.update(db, minutes)


def confirm_minutes(db: Session, minutes_id: str, user_id: str) -> MeetingMinutes:
    minutes = get_owned_minutes(db, minutes_id, user_id)
    if minutes.status != _STATUS_CONFIRMED:
        minutes.status = _STATUS_CONFIRMED
        minutes_repository.update(db, minutes)
    return minutes
