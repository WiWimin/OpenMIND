from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.meeting import Meeting
from app.models.minutes import MeetingMinutes


def create(
    db: Session,
    *,
    minutes_id: str,
    meeting_id: str,
    content: str,
    source_record_ids: list[str],
    status: str = "draft",
) -> MeetingMinutes:
    minutes = MeetingMinutes(
        minutes_id=minutes_id,
        meeting_id=meeting_id,
        content=content,
        source_record_ids=source_record_ids,
        status=status,
    )
    db.add(minutes)
    db.commit()
    db.refresh(minutes)
    return minutes


def get_owned(db: Session, minutes_id: str, user_id: str) -> MeetingMinutes | None:
    statement = (
        select(MeetingMinutes)
        .join(Meeting, MeetingMinutes.meeting_id == Meeting.meeting_id)
        .where(MeetingMinutes.minutes_id == minutes_id, Meeting.user_id == user_id)
    )
    return db.execute(statement).scalar_one_or_none()


def list_by_meeting(
    db: Session, meeting_id: str, *, limit: int, offset: int
) -> list[MeetingMinutes]:
    statement = (
        select(MeetingMinutes)
        .where(MeetingMinutes.meeting_id == meeting_id)
        .order_by(MeetingMinutes.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(db.execute(statement).scalars().all())


def count_by_meeting(db: Session, meeting_id: str) -> int:
    statement = (
        select(func.count())
        .select_from(MeetingMinutes)
        .where(MeetingMinutes.meeting_id == meeting_id)
    )
    return int(db.execute(statement).scalar_one())


def update(db: Session, minutes: MeetingMinutes) -> MeetingMinutes:
    db.commit()
    db.refresh(minutes)
    return minutes
