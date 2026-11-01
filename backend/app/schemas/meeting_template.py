from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class TemplateSource(StrEnum):
    builtin = "builtin"
    custom = "custom"


class MeetingTemplateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    template_id: str
    name: str
    description: str | None = None
    category: str | None = None
    source: TemplateSource
    file_name: str | None = None
    created_at: datetime | None = None
    content_preview: str = ""


class MeetingTemplateDetailRead(MeetingTemplateRead):
    content_text: str


class TemplateTextCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=255)
    category: str | None = Field(default=None, max_length=20)
    content_text: str = Field(min_length=1, max_length=20000)


class TemplateGenerateRequest(BaseModel):
    description: str = Field(min_length=1, max_length=500)


class TemplateGenerateDraft(BaseModel):
    name: str
    description: str | None = None
    category: str | None = None
    content_text: str


class MeetingTemplateDeleteResult(BaseModel):
    deleted: bool = True
