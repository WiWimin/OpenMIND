from __future__ import annotations

from sqlalchemy import delete as sa_delete
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.issue import OpenIssue
from app.models.meeting import Meeting


def create(
    db: Session,
    *,
    issue_id: str,
    meeting_id: str,
    description: str,
    follow_up: str | None,
    source_record_id: str | None,
    status: str = "open",
) -> OpenIssue:
    issue = OpenIssue(
        issue_id=issue_id,
        meeting_id=meeting_id,
        description=description,
        follow_up=follow_up,
        source_record_id=source_record_id,
        status=status,
    )
    db.add(issue)
    db.commit()
    db.refresh(issue)
    return issue


def get_owned(db: Session, issue_id: str, user_id: str) -> OpenIssue | None:
    statement = (
        select(OpenIssue)
        .join(Meeting, OpenIssue.meeting_id == Meeting.meeting_id)
        .where(OpenIssue.issue_id == issue_id, Meeting.user_id == user_id)
    )
    return db.execute(statement).scalar_one_or_none()


def list_by_meeting(
    db: Session, meeting_id: str, *, limit: int, offset: int
) -> list[OpenIssue]:
    statement = (
        select(OpenIssue)
        .where(OpenIssue.meeting_id == meeting_id)
        .order_by(OpenIssue.created_at.asc())
        .limit(limit)
        .offset(offset)
    )
    return list(db.execute(statement).scalars().all())


def count_by_meeting(db: Session, meeting_id: str) -> int:
    statement = (
        select(func.count()).select_from(OpenIssue).where(OpenIssue.meeting_id == meeting_id)
    )
    return int(db.execute(statement).scalar_one())


def update(db: Session, issue: OpenIssue) -> OpenIssue:
    db.commit()
    db.refresh(issue)
    return issue


def delete_by_meeting(db: Session, meeting_id: str) -> None:
    db.execute(sa_delete(OpenIssue).where(OpenIssue.meeting_id == meeting_id))
