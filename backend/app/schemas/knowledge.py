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
    created_at: datetime


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)
    min_score: float = Field(default=0.3, ge=0, le=1)


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
