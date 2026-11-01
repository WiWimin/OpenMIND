from __future__ import annotations

from sqlalchemy.orm import Session

from app.ai.preparation import PreparationDraft, PreparationService
from app.core.exceptions import AppError
from app.models.meeting import Meeting
from app.models.preparation import Preparation
from app.repositories import material_repository, preparation_repository
from app.schemas.preparation import PreparationUpdate
from app.services import meeting_service, meeting_template_service, memory_service
from app.services.model_config_service import (
    ModelConfig,
    ModelPurpose,
    build_llm_client,
    resolve_model_config,
)
from app.utils.ids import new_id

_STATUS_DRAFT = "draft"
_STATUS_CONFIRMED = "confirmed"


def generate_draft(
    meeting: Meeting,
    snippets: list[str],
    user_goal: str | None,
    config: ModelConfig,
    *,
    memory_context: str = "",
    template_instructions: str = "",
) -> PreparationDraft:
    topic_parts = [meeting.title]
    if meeting.topic:
        topic_parts.append(meeting.topic)
    if user_goal:
        topic_parts.append(f"关注点：{user_goal}")
    service = PreparationService(build_llm_client(config))
    return service.generate(
        " / ".join(topic_parts),
        snippets,
        memory_context=memory_context,
        template_instructions=template_instructions,
    )


def _not_found() -> AppError:
    return AppError("RESOURCE_NOT_FOUND", "准备稿不存在或不可访问", http_status=404)


def _history_snippets(
    db: Session, user_id: str, *, max_materials: int = 10, char_limit: int = 20000
) -> list[str]:
    rows = material_repository.list_content_rows(db, user_id)
    snippets: list[str] = []
    used = 0
    for row in reversed(rows):
        content = row.content or ""
        if not content:
            continue
        if used + len(content) > char_limit:
            break
        snippets.append(content)
        used += len(content)
        if len(snippets) >= max_materials:
            break
    return list(reversed(snippets))


def generate_preparation(
    db: Session,
    *,
    meeting_id: str,
    user_id: str,
    user_goal: str | None,
    include_history: bool = True,
    model: str | None = None,
    template_id: str | None = None,
) -> Preparation:
    meeting = meeting_service.get_mutable_meeting(db, meeting_id, user_id)
    snippets = (
        _history_snippets(db, user_id)
        if include_history
        else material_repository.list_contents(db, meeting_id)
    )
    config = resolve_model_config(
        db, user_id, purpose=ModelPurpose.preparation, model_override=model
    )
    template_instructions = (
        meeting_template_service.resolve_template_content(db, user_id, template_id)
        if template_id
        else ""
    )
    memory_context = memory_service.memory_context_for(db, user_id, "preparation")
    draft = generate_draft(
        meeting,
        snippets,
        user_goal,
        config,
        memory_context=memory_context,
        template_instructions=template_instructions,
    )
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
    meeting_service.get_mutable_meeting(db, preparation.meeting_id, user_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(preparation, field, value)
    preparation.version += 1
    return preparation_repository.update(db, preparation)


def confirm_preparation(db: Session, preparation_id: str, user_id: str) -> Preparation:
    preparation = get_owned_preparation(db, preparation_id, user_id)
    meeting_service.get_mutable_meeting(db, preparation.meeting_id, user_id)
    if preparation.status != _STATUS_CONFIRMED:
        preparation.status = _STATUS_CONFIRMED
        preparation_repository.update(db, preparation)
    return preparation
