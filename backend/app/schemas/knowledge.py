from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class KnowledgeStatus(StrEnum):
    uploaded = "uploaded"
    processing = "processing"
    processed = "processed"
    failed = "failed"


class KnowledgeDocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    document_id: str
    file_name: str
    type: str
    processing_status: KnowledgeStatus
    parse_error: str | None
    parse_error_code: str | None = None
    created_at: datetime


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(min_length=1)
    # 缺省时由服务端 RAG_TOP_K / RAG_MIN_SCORE 决定，显式传入优先
    top_k: int | None = Field(default=None, ge=1, le=20)
    min_score: float | None = Field(default=None, ge=0, le=1)


class KnowledgeSearchHit(BaseModel):
    document_id: str
    file_name: str
    excerpt: str
    score: float


class KnowledgeSearchResponse(BaseModel):
    items: list[KnowledgeSearchHit]


class KnowledgeDeleteResult(BaseModel):
    deleted: bool = True
    document_id: str
