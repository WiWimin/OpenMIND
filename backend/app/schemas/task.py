from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class TaskStatus(StrEnum):
    todo = "todo"
    in_progress = "in_progress"
    completed = "completed"
    cancelled = "cancelled"


class TaskPriority(StrEnum):
    high = "high"
    medium = "medium"
    low = "low"


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    due_date: date | None = None
    status: TaskStatus | None = None
    priority: TaskPriority | None = None


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    due_date: date | None = None
    priority: TaskPriority = TaskPriority.medium


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    task_id: str
    user_id: str
    meeting_id: str | None
    action_id: str | None
    title: str
    status: TaskStatus
    priority: TaskPriority
    due_date: date | None
    meeting_title: str | None = None
    created_at: datetime
    updated_at: datetime
