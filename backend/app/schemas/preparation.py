from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class PreparationStatus(StrEnum):
    generating = "generating"
    draft = "draft"
    confirmed = "confirmed"
    failed = "failed"


class PreparationGenerateRequest(BaseModel):
    include_history: bool = True
    user_goal: str | None = None


class PreparationUpdate(BaseModel):
    summary: str | None = None
    checklist: list[str] | None = None


class PreparationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    preparation_id: str
    meeting_id: str
    summary: str
    checklist: list[str]
    status: PreparationStatus
    version: int
    created_at: datetime
    updated_at: datetime
