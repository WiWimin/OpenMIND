from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class TemplateSource(StrEnum):
    builtin = "builtin"
    custom = "custom"


class MeetingTemplateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    template_id: str
    name: str
    description: str | None = None
    source: TemplateSource
    file_name: str | None = None
    created_at: datetime | None = None


class MeetingTemplateDetailRead(MeetingTemplateRead):
    content_text: str


class MeetingTemplateDeleteResult(BaseModel):
    deleted: bool
