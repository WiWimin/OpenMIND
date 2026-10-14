from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class MinutesStatus(StrEnum):
    draft = "draft"
    confirmed = "confirmed"


class MinutesGenerateRequest(BaseModel):
    record_ids: list[str] = Field(default_factory=list)
    include_action_items: bool = False


class MinutesUpdate(BaseModel):
    content: str | None = Field(default=None, min_length=1)


class MinutesRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    minutes_id: str
    meeting_id: str
    content: str
    status: MinutesStatus
    version: int
    source_record_ids: list[str]
    created_at: datetime
    updated_at: datetime
