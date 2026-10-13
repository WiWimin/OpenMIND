from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class RecordType(StrEnum):
    manual = "manual"
    transcript = "transcript"
    imported = "imported"


class RecordCreate(BaseModel):
    content: str = Field(min_length=1)
    record_type: RecordType = RecordType.manual


class RecordUpdate(BaseModel):
    content: str | None = Field(default=None, min_length=1)


class MeetingRecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    record_id: str
    meeting_id: str
    content: str
    record_type: RecordType
    source_material_id: str | None
    created_at: datetime
    updated_at: datetime
