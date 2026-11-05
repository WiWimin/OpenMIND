from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.ai.chat import ChatAnswer, ChatService, RecordContext
from app.ai.prompts import build_organize
from app.ai.rag import VectorRetriever
from app.ai.structured import run_structured
from app.core.exceptions import AppError
from app.repositories import record_repository
from app.schemas.chat import (
    OrganizeTask,
    PolishSuggestions,
    SummaryStructured,
)
from app.services import audio_service, meeting_service, memory_service
from app.services.model_config_service import (
    ModelConfig,
    ModelPurpose,
    build_llm_client,
    resolve_model_config,
)

logger = logging.getLogger(__name__)

# 参与结构化解析的任务：LLM 原始输出需为 JSON
_STRUCTURED_TASKS = {OrganizeTask.summary, OrganizeTask.polish}

_PRIORITY_VALUES = {"high", "medium", "low"}
_CONFIDENCE_VALUES = {"high", "medium", "low"}


def _validate_summary(value: SummaryStructured) -> list[str]:
    """summary 业务字段校验：任务非空、优先级取值合法、原文摘录非空白。"""
    errors: list[str] = []
    for index, item in enumerate(value.action_items):
        if not item.task.strip():  # pragma: no cover — schema min_length 已拦截
            errors.append(f"action_items.{index}.task 不能为空")
        if item.priority not in _PRIORITY_VALUES:
            errors.append(f"action_items.{index}.priority 必须是 high/medium/low")
        if item.source_quote is not None and not item.source_quote.strip():
            errors.append(f"action_items.{index}.source_quote 为空时应使用 null")
    return errors


def _validate_polish(value: PolishSuggestions) -> list[str]:
    """polish 业务字段校验：原文/建议非空、置信度取值合法。"""
    errors: list[str] = []
    for index, item in enumerate(value.root):
        if not item.original.strip():
            errors.append(f"{index}.original 不能为空")
        if not item.suggested.strip():
            errors.append(f"{index}.suggested 不能为空")
        if item.confidence not in _CONFIDENCE_VALUES:
            errors.append(f"{index}.confidence 必须是 high/medium/low")
    return errors


@dataclass(frozen=True)
class OrganizeOutcome:
    task: OrganizeTask
    content: str
    structured: dict | list | None
    source_record_ids: list[str]


def _chat_service(db: Session, user_id: str, model_override: str | None = None) -> ChatService:
    config = resolve_model_config(
        db, user_id, purpose=ModelPurpose.chat, model_override=model_override
    )
    return ChatService(build_llm_client(config), VectorRetriever(db, user_id))


def _run_organize_llm(messages: list[dict[str, str]], config: ModelConfig) -> str:
    return build_llm_client(config).chat(messages).text


def _recent_record_context(
    db: Session, meeting_id: str, *, limit: int = 20, char_limit: int = 8000
) -> list[RecordContext]:
    records = record_repository.list_recent_by_meeting(db, meeting_id, limit=limit)
    selected: list[RecordContext] = []
    used = 0
    for record in reversed(records):
        if used + len(record.content) > char_limit:
            break
        selected.append(
            RecordContext(
                meeting_id=meeting_id,
                record_id=record.record_id,
                content=record.content,
            )
        )
        used += len(record.content)
    return selected


def _resolve_organize_transcripts(
    db: Session,
    *,
    meeting_id: str,
    user_id: str,
    text: str,
    audio_id: str | None,
    record_ids: list[str],
) -> tuple[list[str], list[str]]:
    """输入源三级回退：text > audio_id > record_ids（空 = 最近记录）。"""
    if text and text.strip():
        return [text.strip()], []
    if audio_id:
        audio = audio_service.get_owned_audio(db, audio_id, user_id)
        transcript = (audio.transcript or "").strip()
        if not transcript:
            raise AppError(
                "VALIDATION_ERROR", "该音频尚未成功转写，没有可用的文本", http_status=422
            )
        return [transcript], []
    if record_ids:
        records = record_repository.list_by_ids(db, meeting_id, record_ids)
        if not records:
            raise AppError(
                "VALIDATION_ERROR", "未找到可整理的会议记录", http_status=422
            )
        return [record.content for record in records], [
            record.record_id for record in records
        ]
    contexts = _recent_record_context(db, meeting_id)
    if not contexts:
        raise AppError("VALIDATION_ERROR", "没有可用的会议记录", http_status=422)
    return [ctx.content for ctx in contexts], [ctx.record_id for ctx in contexts]


def chat(
    db: Session,
    *,
    meeting_id: str,
    user_id: str,
    question: str,
    context_scope: str,
    include_sources: bool,
    model: str | None = None,
    mode: str = "plan",
) -> ChatAnswer:
    meeting_service.get_mutable_meeting(db, meeting_id, user_id)
    return _chat_service(db, user_id, model).answer(
        question,
        user_id=user_id,
        scope=context_scope,
        current_meeting_id=meeting_id,
        mode=mode,
        records=(
            []
            if context_scope == "knowledge_base"
            else _recent_record_context(db, meeting_id)
        ),
        memory_context=memory_service.memory_context_for(db, user_id, "chat"),
    )


def organize(
    db: Session,
    *,
    meeting_id: str,
    user_id: str,
    record_ids: list[str],
    style: str = "",
    task: OrganizeTask = OrganizeTask.organize,
    text: str = "",
    instruction: str = "",
    audio_id: str | None = None,
    model: str | None = None,
) -> OrganizeOutcome:
    meeting_service.get_mutable_meeting(db, meeting_id, user_id)
    transcripts, source_ids = _resolve_organize_transcripts(
        db,
        meeting_id=meeting_id,
        user_id=user_id,
        text=text,
        audio_id=audio_id,
        record_ids=record_ids,
    )
    config = resolve_model_config(
        db, user_id, purpose=ModelPurpose.chat, model_override=model
    )
    messages = build_organize(
        {
            "record_transcripts": transcripts,
            "style": style,
            "task": task.value,
            "instruction": instruction,
        }
    )
    if task not in _STRUCTURED_TASKS:
        raw = _run_organize_llm(messages, config)
        return OrganizeOutcome(
            task=task,
            content=raw.strip() or "（未生成有效内容）",
            structured=None,
            source_record_ids=source_ids,
        )

    # summary/polish：结构化管线（预处理 → schema+业务校验 → 1 次修复重试 → 降级原文）
    raw_texts: list[str] = []

    def _fetch(current: list[dict[str, str]]) -> str:
        raw = _run_organize_llm(current, config)
        raw_texts.append(raw)
        return raw

    if task is OrganizeTask.summary:
        parsed = run_structured(
            _fetch,
            messages,
            SummaryStructured,
            scene="organize_summary",
            validator=_validate_summary,
            on_failure="degrade",
        )
        structured: dict | list | None = (
            parsed.model_dump() if parsed is not None else None
        )
    else:
        parsed_polish = run_structured(
            _fetch,
            messages,
            PolishSuggestions,
            scene="organize_polish",
            validator=_validate_polish,
            on_failure="degrade",
        )
        structured = parsed_polish.model_dump() if parsed_polish is not None else None

    # 降级时返回首次尝试的原文（修复重试的输出不作为兜底正文）
    fallback = raw_texts[0] if raw_texts else ""
    content = "" if structured is not None else (fallback.strip() or "（未生成有效内容）")
    return OrganizeOutcome(
        task=task,
        content=content,
        structured=structured,
        source_record_ids=source_ids,
    )
