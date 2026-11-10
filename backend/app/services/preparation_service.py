from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.ai.preparation import PreparationDraft, PreparationService
from app.core.exceptions import resource_not_found
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
from app.utils.pagination import paginate_by

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
    context = prepare_generation_context(
        db,
        meeting_id=meeting_id,
        user_id=user_id,
        user_goal=user_goal,
        include_history=include_history,
        model=model,
        template_id=template_id,
    )
    return run_preparation_generation(db, context)


@dataclass
class PreparationContext:
    """会前准备的同步准备结果：归属校验、素材收集与模型解析（不含 LLM 调用）。"""

    meeting: Meeting
    user_id: str
    snippets: list[str]
    user_goal: str | None
    config: ModelConfig
    template_instructions: str
    memory_context: str


def prepare_generation_context(
    db: Session,
    *,
    meeting_id: str,
    user_id: str,
    user_goal: str | None,
    include_history: bool = True,
    model: str | None = None,
    template_id: str | None = None,
) -> PreparationContext:
    """同步校验与上下文收集：404 归属、400 模型未配置等在受理前同步返回。"""
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
    return PreparationContext(
        meeting=meeting,
        user_id=user_id,
        snippets=snippets,
        user_goal=user_goal,
        config=config,
        template_instructions=template_instructions,
        memory_context=memory_context,
    )


def create_generating(db: Session, *, meeting_id: str) -> Preparation:
    """异步受理时先落一条 `generating` 占位行，由后台任务转 `draft`/`failed`。"""
    return preparation_repository.create(
        db,
        preparation_id=new_id("prep"),
        meeting_id=meeting_id,
        summary="",
        checklist=[],
        status="generating",
    )


def run_preparation_generation(
    db: Session,
    context: PreparationContext,
    *,
    preparation_id: str | None = None,
    progress_cb: Callable[[int], None] | None = None,
) -> Preparation:
    """LLM 生成准备稿并落库；`preparation_id` 为异步占位行 id（同步路径为 None）。

    失败以 `AppError` 上抛，由调用方（任务执行器）把占位行标为 `failed`。
    """
    if progress_cb:
        progress_cb(20)
    draft = generate_draft(
        context.meeting,
        context.snippets,
        context.user_goal,
        context.config,
        memory_context=context.memory_context,
        template_instructions=context.template_instructions,
    )
    if progress_cb:
        progress_cb(80)
    if preparation_id is None:
        return preparation_repository.create(
            db,
            preparation_id=new_id("prep"),
            meeting_id=context.meeting.meeting_id,
            summary=draft.summary,
            checklist=draft.checklist,
            status=_STATUS_DRAFT,
        )
    preparation = _get_by_id(db, preparation_id)
    preparation.summary = draft.summary
    preparation.checklist = draft.checklist
    preparation.status = _STATUS_DRAFT
    return preparation_repository.update(db, preparation)


def _get_by_id(db: Session, preparation_id: str) -> Preparation:
    preparation = preparation_repository.get_by_id(db, preparation_id)
    if preparation is None:
        raise resource_not_found("准备稿")
    return preparation


def mark_generation_failed(db: Session, preparation_id: str) -> None:
    """异步生成失败：占位行标 `failed`（保留记录，可再次生成覆盖）。"""
    preparation = _get_by_id(db, preparation_id)
    if preparation.status == "generating":
        preparation.status = "failed"
        preparation_repository.update(db, preparation)


def list_preparations(
    db: Session, *, meeting_id: str, user_id: str, page: int, page_size: int
) -> tuple[list[Preparation], int]:
    meeting_service.get_owned_meeting(db, meeting_id, user_id)
    return paginate_by(
        preparation_repository.list_by_meeting,
        preparation_repository.count_by_meeting,
        db,
        meeting_id,
        page=page,
        page_size=page_size,
    )


def get_owned_preparation(db: Session, preparation_id: str, user_id: str) -> Preparation:
    preparation = preparation_repository.get_owned(db, preparation_id, user_id)
    if preparation is None:
        raise resource_not_found("准备稿")
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
