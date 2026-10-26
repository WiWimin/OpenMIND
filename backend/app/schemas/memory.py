from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.minutes import MinutesTemplate


class MemoryWrite(BaseModel):
    role: str | None = Field(default=None, max_length=100)
    work_scenarios: str | None = Field(default=None, max_length=2000)
    communication_style: str | None = Field(default=None, max_length=2000)
    preferred_minutes_template: MinutesTemplate | None = None


class MemoryRead(BaseModel):
    role: str
    work_scenarios: str
    communication_style: str
    preferred_minutes_template: MinutesTemplate | None
    updated_at: datetime | None


class MemoryDeleteResult(BaseModel):
    deleted: bool = True
