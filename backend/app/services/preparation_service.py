from __future__ import annotations

from sqlalchemy.orm import Session

from app.ai.llm import LLMClient
from app.ai.preparation import PreparationDraft, PreparationService
from app.core.exceptions import AppError
from app.models.meeting import Meeting
from app.models.preparation import Preparation
from app.repositories import material_repository, preparation_repository
from app.schemas.preparation import PreparationUpdate
from app.services import meeting_service
from app.utils.ids import new_id

_STATUS_DRAFT = "draft"
_STATUS_CONFIRMED = "confirmed"


def generate_draft(
    meeting: Meeting, snippets: list[str], user_goal: str | None
) -> PreparationDraft:
    topic_parts = [meeting.title]
    if meeting.topic:
        topic_parts.append(meeting.topic)
    if user_goal:
        topic_parts.append(f"关注点：{user_goal}")
    service = PreparationService(LLMClient())
    return service.generate(" / ".join(topic_parts), snippets)


def _not_found() -> AppError:
    return AppError("RESOURCE_NOT_FOUND", "准备稿不存在或不可访问", http_status=404)


def generate_preparation(
    db: Session, *, meeting_id: str, user_id: str, user_goal: str | None
) -> Preparation:
    meeting = meeting_service.get_owned_meeting(db, meeting_id, user_id)
    snippets = material_repository.list_contents(db, meeting_id)
    draft = generate_draft(meeting, snippets, user_goal)
    return preparation_repository.create(
        db,
        preparation_id=new_id("prep"),
        meeting_id=meeting_id,
        summary=draft.summary,
        checklist=draft.checklist,
        status=_STATUS_DRAFT,
    )


def list_preparations(
    db: Session, *, meeting_id: str, user_id: str, page: int, page_size: int
) -> tuple[list[Preparation], int]:
    meeting_service.get_owned_meeting(db, meeting_id, user_id)
    offset = (page - 1) * page_size
    items = preparation_repository.list_by_meeting(
        db, meeting_id, limit=page_size, offset=offset
    )
    total = preparation_repository.count_by_meeting(db, meeting_id)
    return items, total


def get_owned_preparation(db: Session, preparation_id: str, user_id: str) -> Preparation:
    preparation = preparation_repository.get_owned(db, preparation_id, user_id)
    if preparation is None:
        raise _not_found()
    return preparation


def update_preparation(
    db: Session, preparation_id: str, user_id: str, payload: PreparationUpdate
) -> Preparation:
    preparation = get_owned_preparation(db, preparation_id, user_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(preparation, field, value)
    preparation.version += 1
    return preparation_repository.update(db, preparation)


def confirm_preparation(db: Session, preparation_id: str, user_id: str) -> Preparation:
    preparation = get_owned_preparation(db, preparation_id, user_id)
    if preparation.status != _STATUS_CONFIRMED:
        preparation.status = _STATUS_CONFIRMED
        preparation_repository.update(db, preparation)
    return preparation
