from __future__ import annotations

from sqlalchemy.orm import Session

from app.ai.chat import ChatAnswer, ChatService
from app.ai.llm import LLMClient
from app.ai.prompts import build_organize
from app.core.exceptions import AppError
from app.repositories import record_repository
from app.services import meeting_service
from app.services.retrieval_service import MaterialContentRetriever


def _chat_service(db: Session, user_id: str) -> ChatService:
    return ChatService(LLMClient(), MaterialContentRetriever(db, user_id))


def _organize_text(transcripts: list[str], style: str) -> str:
    messages = build_organize({"record_transcripts": transcripts, "style": style})
    return LLMClient().chat(messages).text


def chat(
    db: Session,
    *,
    meeting_id: str,
    user_id: str,
    question: str,
    context_scope: str,
    include_sources: bool,
) -> ChatAnswer:
    meeting_service.get_owned_meeting(db, meeting_id, user_id)
    return _chat_service(db, user_id).answer(
        question,
        user_id=user_id,
        scope=context_scope,
        current_meeting_id=meeting_id,
    )


def organize(
    db: Session,
    *,
    meeting_id: str,
    user_id: str,
    record_ids: list[str],
    style: str,
) -> tuple[str, list[str]]:
    meeting_service.get_owned_meeting(db, meeting_id, user_id)
    records = record_repository.list_by_ids(db, meeting_id, record_ids)
    if not records:
        raise AppError("VALIDATION_ERROR", "未找到可整理的会议记录", http_status=422)
    transcripts = [record.content for record in records]
    organized = _organize_text(transcripts, style)
    return organized, [record.record_id for record in records]
