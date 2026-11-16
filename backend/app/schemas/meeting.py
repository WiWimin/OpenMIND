from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class MeetingStatus(StrEnum):
    scheduled = "scheduled"
    archived = "archived"


class MeetingCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    topic: str | None = None
    meeting_time: datetime | None = None


class MeetingUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    topic: str | None = None
    meeting_time: datetime | None = None


class MeetingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    meeting_id: str
    title: str
    topic: str | None
    meeting_time: datetime | None
    status: MeetingStatus
    # 卡片展示元信息（仅列表接口填充，其余接口为默认值）
    has_minutes: bool = False
    material_count: int = 0
    record_count: int = 0
    audio_count: int = 0
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None
