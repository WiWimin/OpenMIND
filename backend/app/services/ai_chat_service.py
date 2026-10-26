from __future__ import annotations

from sqlalchemy.orm import Session

from app.ai.chat import ChatAnswer, ChatService, RecordContext
from app.ai.prompts import build_organize
from app.ai.rag import VectorRetriever
from app.core.exceptions import AppError
from app.repositories import record_repository
from app.services import meeting_service
from app.services.model_config_service import (
    ModelConfig,
    ModelPurpose,
    build_llm_client,
    resolve_model_config,
)


def _chat_service(db: Session, user_id: str) -> ChatService:
    config = resolve_model_config(db, user_id, purpose=ModelPurpose.chat)
    return ChatService(build_llm_client(config), VectorRetriever(db, user_id))


def _organize_text(transcripts: list[str], style: str, config: ModelConfig) -> str:
    messages = build_organize({"record_transcripts": transcripts, "style": style})
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


def chat(
    db: Session,
    *,
    meeting_id: str,
    user_id: str,
    question: str,
    context_scope: str,
    include_sources: bool,
) -> ChatAnswer:
    meeting_service.get_mutable_meeting(db, meeting_id, user_id)
    return _chat_service(db, user_id).answer(
        question,
        user_id=user_id,
        scope=context_scope,
        current_meeting_id=meeting_id,
        records=_recent_record_context(db, meeting_id),
    )


def organize(
    db: Session,
    *,
    meeting_id: str,
    user_id: str,
    record_ids: list[str],
    style: str,
) -> tuple[str, list[str]]:
    meeting_service.get_mutable_meeting(db, meeting_id, user_id)
    records = record_repository.list_by_ids(db, meeting_id, record_ids)
    if not records:
        raise AppError("VALIDATION_ERROR", "未找到可整理的会议记录", http_status=422)
    transcripts = [record.content for record in records]
    config = resolve_model_config(db, user_id, purpose=ModelPurpose.chat)
    organized = _organize_text(transcripts, style, config)
    return organized, [record.record_id for record in records]
