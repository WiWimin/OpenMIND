from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class ChatContextScope(StrEnum):
    current_meeting = "current_meeting"
    current_and_history = "current_and_history"


class ChatRequest(BaseModel):
    question: str = Field(min_length=1)
    context_scope: ChatContextScope = ChatContextScope.current_and_history
    include_sources: bool = True


class ChatSource(BaseModel):
    meeting_id: str
    material_id: str
    record_id: str | None
    excerpt: str


class ChatResponse(BaseModel):
    answer: str
    sources: list[ChatSource]
    insufficient_evidence: bool


class OrganizeRequest(BaseModel):
    record_ids: list[str] = Field(min_length=1)
    style: str = "structured"


class OrganizeResponse(BaseModel):
    organized_content: str
    source_record_ids: list[str]
