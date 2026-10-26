from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class AudioStatus(StrEnum):
    uploaded = "uploaded"
    processing = "processing"
    transcribed = "transcribed"
    failed = "failed"
    confirmed = "confirmed"


class AudioRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    audio_id: str
    meeting_id: str
    file_name: str
    type: str
    status: AudioStatus
    transcript: str | None
    error: str | None
    record_id: str | None
    created_at: datetime
    updated_at: datetime


class AudioUpdate(BaseModel):
    transcript: str = Field(min_length=1)


class AudioDeleteResult(BaseModel):
    deleted: bool = True
    audio_id: str
