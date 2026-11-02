from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ActionItemStatus(StrEnum):
    pending_confirmation = "pending_confirmation"
    confirmed = "confirmed"
    converted = "converted"
    cancelled = "cancelled"


class ActionItemSource(BaseModel):
    record_id: str | None = None
    excerpt: str | None = None


class ActionItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    action_id: str
    meeting_id: str
    content: str
    assignee: str | None
    due_date: date | None
    status: ActionItemStatus
    source: ActionItemSource
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="before")
    @classmethod
    def _flatten_source(cls, data: Any) -> Any:
        """把 ORM 的扁平 source_record_id / source_excerpt 列映射为嵌套 source。"""
        if not isinstance(data, dict) and hasattr(data, "source_record_id"):
            return {
                "action_id": data.action_id,
                "meeting_id": data.meeting_id,
                "content": data.content,
                "assignee": data.assignee,
                "due_date": data.due_date,
                "status": data.status,
                "source": {
                    "record_id": data.source_record_id,
                    "excerpt": data.source_excerpt,
                },
                "created_at": data.created_at,
                "updated_at": data.updated_at,
            }
        return data


class ActionItemExtractRequest(BaseModel):
    record_ids: list[str] = Field(default_factory=list)


class ActionItemExtractResult(BaseModel):
    items: list[ActionItemRead]


class ActionItemUpdate(BaseModel):
    content: str | None = Field(default=None, min_length=1)
    assignee: str | None = None
    due_date: date | None = None


class ConvertToTaskRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    due_date: date | None = None
