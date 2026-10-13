from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ChatSource,
    OrganizeRequest,
    OrganizeResponse,
)
from app.schemas.common import Envelope
from app.services import ai_chat_service

router = APIRouter(tags=["ai"])


@router.post("/meetings/{meeting_id}/chat", response_model=Envelope[ChatResponse])
def chat(
    meeting_id: str,
    payload: ChatRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> Envelope[ChatResponse]:
    answer = ai_chat_service.chat(
        db,
        meeting_id=meeting_id,
        user_id=current_user.user_id,
        question=payload.question,
        context_scope=payload.context_scope.value,
        include_sources=payload.include_sources,
    )
    sources = (
        [
            ChatSource(
                meeting_id=source.meeting_id,
                material_id=source.material_id,
                record_id=source.record_id,
                excerpt=source.excerpt,
            )
            for source in answer.sources
        ]
        if payload.include_sources
        else []
    )
    return Envelope(
        data=ChatResponse(
            answer=answer.answer,
            sources=sources,
            insufficient_evidence=answer.insufficient_evidence,
        )
    )


@router.post("/meetings/{meeting_id}/organize", response_model=Envelope[OrganizeResponse])
def organize(
    meeting_id: str,
    payload: OrganizeRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> Envelope[OrganizeResponse]:
    organized_content, source_record_ids = ai_chat_service.organize(
        db,
        meeting_id=meeting_id,
        user_id=current_user.user_id,
        record_ids=payload.record_ids,
        style=payload.style,
    )
    return Envelope(
        data=OrganizeResponse(
            organized_content=organized_content,
            source_record_ids=source_record_ids,
        )
    )
