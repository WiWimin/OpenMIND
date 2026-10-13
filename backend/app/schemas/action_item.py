from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class ActionItemStatus(StrEnum):
    pending_confirmation = "pending_confirmation"
    confirmed = "confirmed"
    converted = "converted"
    cancelled = "cancelled"


class ActionItemSource(BaseModel):
    record_id: str | None = None
    excerpt: str | None = None


class ActionItemRead(BaseModel):
    action_id: str
    meeting_id: str
    content: str
    assignee: str | None
    due_date: date | None
    status: ActionItemStatus
    source: ActionItemSource
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, item: object) -> ActionItemRead:
        return cls(
            action_id=item.action_id,
            meeting_id=item.meeting_id,
            content=item.content,
            assignee=item.assignee,
            due_date=item.due_date,
            status=item.status,
            source=ActionItemSource(
                record_id=item.source_record_id,
                excerpt=item.source_excerpt,
            ),
            created_at=item.created_at,
            updated_at=item.updated_at,
        )


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
