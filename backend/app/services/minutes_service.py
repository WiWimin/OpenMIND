from __future__ import annotations

from sqlalchemy.orm import Session

from app.ai.minutes import MinutesService
from app.core.exceptions import AppError
from app.models.meeting import Meeting
from app.models.minutes import MeetingMinutes
from app.models.record import MeetingRecord
from app.repositories import material_repository, minutes_repository, record_repository
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
_MAX_MATERIALS = 10
_MAX_MATERIAL_CHARS = 12000


def generate_text(
    meeting: Meeting,
    transcripts: list[str],
    config: ModelConfig,
    *,
    material_snippets: list[str] | None = None,
    marked_records: list[dict[str, str]] | None = None,
    template: str = "standard",
) -> str:
    topic_parts = [meeting.title]
    if meeting.topic:
        topic_parts.append(meeting.topic)
    return MinutesService(build_llm_client(config)).generate(
        " / ".join(topic_parts),
        transcripts,
        material_snippets or [],
        marked_records or [],
        template=template,
    )


def _not_found() -> AppError:
    return AppError("RESOURCE_NOT_FOUND", "纪要不存在或不可访问", http_status=404)


def _gather_records(
    db: Session, meeting_id: str, record_ids: list[str]
) -> list[MeetingRecord]:
    if record_ids:
        return record_repository.list_by_ids(db, meeting_id, record_ids)
    return record_repository.list_by_meeting(
        db, meeting_id, limit=_MAX_RECORDS, offset=0
    )


def _gather_materials(
    db: Session, meeting_id: str, *, enabled: bool
) -> tuple[list[str], list[str]]:
    if not enabled:
        return [], []
    snippets: list[str] = []
    material_ids: list[str] = []
    used = 0
    for material in material_repository.list_all_by_meeting(db, meeting_id):
        content = material.content or ""
        if not content:
            continue
        remaining = _MAX_MATERIAL_CHARS - used
        if remaining <= 0:
            break
        snippet = content[:remaining]
        snippets.append(snippet)
        material_ids.append(material.material_id)
        used += len(snippet)
        if len(snippet) < len(content) or len(snippets) >= _MAX_MATERIALS:
            break
    return snippets, material_ids


def generate_minutes(
    db: Session, *, meeting_id: str, user_id: str, payload: MinutesGenerateRequest
) -> MeetingMinutes:
    meeting = meeting_service.get_mutable_meeting(db, meeting_id, user_id)
    records = _gather_records(db, meeting_id, payload.record_ids)
    transcripts = [record.content for record in records]
    record_ids = [record.record_id for record in records]
    marked_records = [
        {
            "record_id": record.record_id,
            "marker_type": record.marker_type,
            "content": record.content,
        }
        for record in records
        if record.marker_type
    ]
    material_snippets, material_ids = _gather_materials(
        db, meeting_id, enabled=payload.include_materials
    )
    config = resolve_model_config(db, user_id)
    content = generate_text(
        meeting,
        transcripts,
        config,
        material_snippets=material_snippets,
        marked_records=marked_records,
        template=payload.template.value,
    )
    minutes = minutes_repository.create(
        db,
        minutes_id=new_id("min"),
        meeting_id=meeting_id,
        content=content,
        source_record_ids=record_ids,
        source_material_ids=material_ids,
        template=payload.template.value,
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
    meeting_service.get_mutable_meeting(db, minutes.meeting_id, user_id)
    data = payload.model_dump(exclude_unset=True)
    if data.get("content") is not None:
        minutes.content = data["content"]
    minutes.version += 1
    return minutes_repository.update(db, minutes)


def confirm_minutes(db: Session, minutes_id: str, user_id: str) -> MeetingMinutes:
    minutes = get_owned_minutes(db, minutes_id, user_id)
    meeting_service.get_mutable_meeting(db, minutes.meeting_id, user_id)
    if minutes.status != _STATUS_CONFIRMED:
        minutes.status = _STATUS_CONFIRMED
        minutes_repository.update(db, minutes)
    return minutes
