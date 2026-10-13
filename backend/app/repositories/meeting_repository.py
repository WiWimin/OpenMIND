from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.meeting import Meeting


def list_by_user(
    db: Session,
    user_id: str,
    *,
    status: str | None,
    limit: int,
    offset: int,
) -> list[Meeting]:
    statement = select(Meeting).where(Meeting.user_id == user_id)
    if status is not None:
        statement = statement.where(Meeting.status == status)
    statement = statement.order_by(
        Meeting.meeting_time.desc().nullslast(), Meeting.created_at.desc()
    )
    statement = statement.limit(limit).offset(offset)
    return list(db.execute(statement).scalars().all())


def count_by_user(db: Session, user_id: str, *, status: str | None) -> int:
    statement = select(func.count()).select_from(Meeting).where(Meeting.user_id == user_id)
    if status is not None:
        statement = statement.where(Meeting.status == status)
    return int(db.execute(statement).scalar_one())


def get_owned(db: Session, meeting_id: str, user_id: str) -> Meeting | None:
    return db.execute(
        select(Meeting).where(Meeting.meeting_id == meeting_id, Meeting.user_id == user_id)
    ).scalar_one_or_none()


def create(
    db: Session,
    *,
    meeting_id: str,
    user_id: str,
    title: str,
    topic: str | None,
    meeting_time: datetime | None,
) -> Meeting:
    meeting = Meeting(
        meeting_id=meeting_id,
        user_id=user_id,
        title=title,
        topic=topic,
        meeting_time=meeting_time,
    )
    db.add(meeting)
    db.commit()
    db.refresh(meeting)
    return meeting


def update(db: Session, meeting: Meeting) -> Meeting:
    db.commit()
    db.refresh(meeting)
    return meeting


def delete(db: Session, meeting: Meeting) -> None:
    db.delete(meeting)
    db.commit()
