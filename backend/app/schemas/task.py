from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class TaskStatus(StrEnum):
    todo = "todo"
    in_progress = "in_progress"
    completed = "completed"
    cancelled = "cancelled"


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    due_date: date | None = None
    status: TaskStatus | None = None


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    task_id: str
    user_id: str
    meeting_id: str | None
    action_id: str | None
    title: str
    status: TaskStatus
    due_date: date | None
    created_at: datetime
    updated_at: datetime
