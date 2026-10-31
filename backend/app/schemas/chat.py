from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class ChatContextScope(StrEnum):
    current_meeting = "current_meeting"
    current_and_history = "current_and_history"
    knowledge_base = "knowledge_base"


class ChatRequest(BaseModel):
    question: str = Field(min_length=1)
    context_scope: ChatContextScope = ChatContextScope.current_meeting
    include_sources: bool = True
    # 可选：覆盖本次对话使用的模型名，必须已在模型配置中登记
    model: str | None = Field(default=None, max_length=100)


class ChatSource(BaseModel):
    meeting_id: str | None
    material_id: str | None
    record_id: str | None
    document_id: str | None = None
    document_name: str | None = None
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
