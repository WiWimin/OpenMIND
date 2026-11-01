from __future__ import annotations

import json
import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.ai.chat import ChatAnswer, ChatService, RecordContext
from app.ai.prompts import build_organize
from app.ai.rag import VectorRetriever
from app.core.exceptions import AppError
from app.repositories import record_repository
from app.schemas.chat import OrganizeTask
from app.services import audio_service, meeting_service, memory_service
from app.services.model_config_service import (
    ModelConfig,
    ModelPurpose,
    build_llm_client,
    resolve_model_config,
)

# 参与结构化解析的任务：LLM 原始输出需为 JSON
_STRUCTURED_TASKS = {OrganizeTask.summary, OrganizeTask.polish}


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


def _strip_json_fence(raw: str) -> str:
    cleaned = raw.strip()
    cleaned = re.sub(r"^```[a-zA-Z]*\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def _parse_structured(raw: str) -> dict | list | None:
    """容错解析 LLM 输出的 JSON：剥离代码块标记，失败时截取首尾括号重试。"""
    cleaned = _strip_json_fence(raw)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        starts = [i for i in (cleaned.find("{"), cleaned.find("[")) if i != -1]
        ends = [i for i in (cleaned.rfind("}"), cleaned.rfind("]")) if i != -1]
        if not starts or not ends:
            return None
        start, end = min(starts), max(ends)
        if end <= start:
            return None
        try:
            parsed = json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError:
            return None
    return parsed if isinstance(parsed, (dict, list)) else None


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
) -> ChatAnswer:
    meeting_service.get_mutable_meeting(db, meeting_id, user_id)
    return _chat_service(db, user_id, model).answer(
        question,
        user_id=user_id,
        scope=context_scope,
        current_meeting_id=meeting_id,
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
    raw = _run_organize_llm(messages, config)
    structured = _parse_structured(raw) if task in _STRUCTURED_TASKS else None
    content = "" if structured is not None else (raw.strip() or "（未生成有效内容）")
    return OrganizeOutcome(
        task=task,
        content=content,
        structured=structured,
        source_record_ids=source_ids,
    )
