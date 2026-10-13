from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.meeting import Meeting
from app.models.record import MeetingRecord


def create(
    db: Session,
    *,
    record_id: str,
    meeting_id: str,
    content: str,
    record_type: str,
    source_material_id: str | None = None,
) -> MeetingRecord:
    record = MeetingRecord(
        record_id=record_id,
        meeting_id=meeting_id,
        content=content,
        record_type=record_type,
        source_material_id=source_material_id,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def get_owned(db: Session, record_id: str, user_id: str) -> MeetingRecord | None:
    statement = (
        select(MeetingRecord)
        .join(Meeting, MeetingRecord.meeting_id == Meeting.meeting_id)
        .where(
            MeetingRecord.record_id == record_id,
            Meeting.user_id == user_id,
        )
    )
    return db.execute(statement).scalar_one_or_none()


def list_by_meeting(
    db: Session, meeting_id: str, *, limit: int, offset: int
) -> list[MeetingRecord]:
    statement = (
        select(MeetingRecord)
        .where(MeetingRecord.meeting_id == meeting_id)
        .order_by(MeetingRecord.created_at.asc())
        .limit(limit)
        .offset(offset)
    )
    return list(db.execute(statement).scalars().all())


def count_by_meeting(db: Session, meeting_id: str) -> int:
    statement = (
        select(func.count())
        .select_from(MeetingRecord)
        .where(MeetingRecord.meeting_id == meeting_id)
    )
    return int(db.execute(statement).scalar_one())


def list_by_ids(
    db: Session, meeting_id: str, record_ids: list[str]
) -> list[MeetingRecord]:
    statement = (
        select(MeetingRecord)
        .where(
            MeetingRecord.meeting_id == meeting_id,
            MeetingRecord.record_id.in_(record_ids),
        )
        .order_by(MeetingRecord.created_at.asc())
    )
    return list(db.execute(statement).scalars().all())


def update(db: Session, record: MeetingRecord) -> MeetingRecord:
    db.commit()
    db.refresh(record)
    return record


def delete(db: Session, record: MeetingRecord) -> None:
    db.delete(record)
    db.commit()
