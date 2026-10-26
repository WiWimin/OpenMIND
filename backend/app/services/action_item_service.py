from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.ai.extraction import ActionItemCandidate, ActionItemExtractor
from app.core.exceptions import AppError
from app.models.action_item import ActionItem
from app.models.record import MeetingRecord
from app.models.task import PersonalTask
from app.repositories import action_item_repository, record_repository, task_repository
from app.schemas.action_item import ActionItemUpdate, ConvertToTaskRequest
from app.services import meeting_service
from app.services.model_config_service import (
    ModelConfig,
    build_llm_client,
    resolve_model_config,
)
from app.utils.ids import new_id

_PENDING = "pending_confirmation"
_CONFIRMED = "confirmed"
_CONVERTED = "converted"
_MAX_RECORDS = 100


def extract_candidates(
    transcripts: list[str], config: ModelConfig
) -> list[ActionItemCandidate]:
    return ActionItemExtractor(build_llm_client(config)).extract(transcripts)


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _not_found() -> AppError:
    return AppError("RESOURCE_NOT_FOUND", "行动项不存在或不可访问", http_status=404)


def _gather_records(
    db: Session, meeting_id: str, record_ids: list[str]
) -> list[MeetingRecord]:
    if record_ids:
        return record_repository.list_by_ids(db, meeting_id, record_ids)
    return record_repository.list_by_meeting(
        db, meeting_id, limit=_MAX_RECORDS, offset=0
    )


def _source_record(
    records: list[MeetingRecord], candidate: ActionItemCandidate
) -> tuple[str | None, str | None]:
    valid_ids = {record.record_id for record in records}
    source_id = candidate.source_record_id
    if source_id is None:
        source_id = records[0].record_id if len(records) == 1 else None
    elif source_id not in valid_ids:
        source_id = None
    if source_id is None:
        return None, None
    record = next(record for record in records if record.record_id == source_id)
    excerpt = candidate.source_excerpt
    if not excerpt or excerpt not in record.content:
        excerpt = record.content[:200] or None
    return source_id, excerpt


def extract_action_items(
    db: Session, *, meeting_id: str, user_id: str, record_ids: list[str]
) -> list[ActionItem]:
    meeting_service.get_mutable_meeting(db, meeting_id, user_id)
    records = _gather_records(db, meeting_id, record_ids)
    transcripts = [f"[{record.record_id}] {record.content}" for record in records]
    config = resolve_model_config(db, user_id)
    candidates = extract_candidates(transcripts, config)
    items: list[ActionItem] = []
    for candidate in candidates:
        source_record_id, source_excerpt = _source_record(records, candidate)
        items.append(
            action_item_repository.create(
                db,
                action_id=new_id("act"),
                meeting_id=meeting_id,
                content=candidate.content,
                assignee=candidate.assignee,
                due_date=_parse_date(candidate.due_date),
                source_record_id=source_record_id,
                source_excerpt=source_excerpt,
                status=_PENDING,
            )
        )
    return items


def list_action_items(
    db: Session, *, meeting_id: str, user_id: str, page: int, page_size: int
) -> tuple[list[ActionItem], int]:
    meeting_service.get_owned_meeting(db, meeting_id, user_id)
    offset = (page - 1) * page_size
    items = action_item_repository.list_by_meeting(
        db, meeting_id, limit=page_size, offset=offset
    )
    total = action_item_repository.count_by_meeting(db, meeting_id)
    return items, total


def get_owned_action_item(db: Session, action_id: str, user_id: str) -> ActionItem:
    item = action_item_repository.get_owned(db, action_id, user_id)
    if item is None:
        raise _not_found()
    return item


def update_action_item(
    db: Session, action_id: str, user_id: str, payload: ActionItemUpdate
) -> ActionItem:
    item = get_owned_action_item(db, action_id, user_id)
    meeting_service.get_mutable_meeting(db, item.meeting_id, user_id)
    data = payload.model_dump(exclude_unset=True)
    if data.get("content") is not None:
        item.content = data["content"]
    if "assignee" in data:
        item.assignee = data["assignee"]
    if "due_date" in data:
        item.due_date = data["due_date"]
    return action_item_repository.update(db, item)


def confirm_action_item(db: Session, action_id: str, user_id: str) -> ActionItem:
    item = get_owned_action_item(db, action_id, user_id)
    meeting_service.get_mutable_meeting(db, item.meeting_id, user_id)
    if item.status == _PENDING:
        item.status = _CONFIRMED
        action_item_repository.update(db, item)
    return item


def delete_action_item(db: Session, action_id: str, user_id: str) -> None:
    item = get_owned_action_item(db, action_id, user_id)
    meeting_service.get_mutable_meeting(db, item.meeting_id, user_id)
    if item.status == _CONVERTED:
        raise AppError(
            "BUSINESS_RULE_VIOLATION", "已转为任务的行动项不可删除", http_status=409
        )
    action_item_repository.delete(db, item)


def convert_to_task(
    db: Session, *, action_id: str, user_id: str, payload: ConvertToTaskRequest
) -> tuple[PersonalTask, bool]:
    item = get_owned_action_item(db, action_id, user_id)
    meeting_service.get_mutable_meeting(db, item.meeting_id, user_id)
    existing = task_repository.get_by_action(db, action_id)
    if existing is not None:
        return existing, False
    if item.status != _CONFIRMED:
        raise AppError(
            "BUSINESS_RULE_VIOLATION", "仅已确认的行动项可转为任务", http_status=409
        )
    task = task_repository.create(
        db,
        task_id=new_id("tsk"),
        user_id=user_id,
        meeting_id=item.meeting_id,
        action_id=action_id,
        title=payload.title,
        due_date=payload.due_date if payload.due_date is not None else item.due_date,
    )
    item.status = _CONVERTED
    action_item_repository.update(db, item)
    return task, True
