from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class IssueStatus(StrEnum):
    open = "open"
    resolved = "resolved"
    cancelled = "cancelled"


class IssueSource(BaseModel):
    record_id: str | None = None


class IssueRead(BaseModel):
    issue_id: str
    meeting_id: str
    description: str
    status: IssueStatus
    follow_up: str | None
    source: IssueSource
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, issue: object) -> IssueRead:
        return cls(
            issue_id=issue.issue_id,
            meeting_id=issue.meeting_id,
            description=issue.description,
            status=issue.status,
            follow_up=issue.follow_up,
            source=IssueSource(record_id=issue.source_record_id),
            created_at=issue.created_at,
            updated_at=issue.updated_at,
        )


class IssueExtractRequest(BaseModel):
    record_ids: list[str] = Field(default_factory=list)


class IssueExtractResult(BaseModel):
    items: list[IssueRead]


class IssueUpdate(BaseModel):
    description: str | None = Field(default=None, min_length=1)
    status: IssueStatus | None = None
    follow_up: str | None = None
