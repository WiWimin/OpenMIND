from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class IssueStatus(StrEnum):
    open = "open"
    resolved = "resolved"
    cancelled = "cancelled"


class IssueSource(BaseModel):
    record_id: str | None = None


class IssueRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    issue_id: str
    meeting_id: str
    description: str
    status: IssueStatus
    follow_up: str | None
    source: IssueSource
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="before")
    @classmethod
    def _flatten_source(cls, data: Any) -> Any:
        """把 ORM 的扁平 source_record_id 列映射为嵌套 source。"""
        if not isinstance(data, dict) and hasattr(data, "source_record_id"):
            return {
                "issue_id": data.issue_id,
                "meeting_id": data.meeting_id,
                "description": data.description,
                "status": data.status,
                "follow_up": data.follow_up,
                "source": {"record_id": data.source_record_id},
                "created_at": data.created_at,
                "updated_at": data.updated_at,
            }
        return data


class IssueExtractRequest(BaseModel):
    record_ids: list[str] = Field(default_factory=list)


class IssueExtractResult(BaseModel):
    items: list[IssueRead]


class IssueUpdate(BaseModel):
    description: str | None = Field(default=None, min_length=1)
    status: IssueStatus | None = None
    follow_up: str | None = None
