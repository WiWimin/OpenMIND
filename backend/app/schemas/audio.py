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


class AudioSegment(BaseModel):
    """转写分段：seq 从 1 连续递增，offset_seconds 为录音内相对秒数。"""

    seq: int
    offset_seconds: int = 0
    text: str = ""
    marker_type: str | None = None
    error: str | None = None


class AudioRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    audio_id: str
    meeting_id: str
    file_name: str
    type: str
    status: AudioStatus
    transcript: str | None
    segments: list[AudioSegment] | None
    error: str | None
    record_id: str | None
    created_at: datetime
    updated_at: datetime


class AudioUpdate(BaseModel):
    transcript: str = Field(min_length=1)


class AudioLiveStart(BaseModel):
    file_type: str = Field(default="webm", max_length=10)


class AudioLiveChunkResult(BaseModel):
    audio_id: str
    seq: int
    text: str
    error: str | None = None
    transcript: str | None


class AudioSegmentMarkerUpdate(BaseModel):
    seq: int = Field(ge=1)
    marker_type: str | None = None


class AudioDeleteResult(BaseModel):
    deleted: bool = True
    audio_id: str
