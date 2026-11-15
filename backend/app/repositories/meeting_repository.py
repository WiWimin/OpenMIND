from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.audio import MeetingAudio
from app.models.material import MeetingMaterial
from app.models.meeting import Meeting
from app.models.minutes import MeetingMinutes
from app.models.record import MeetingRecord


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


def titles_by_ids(
    db: Session, user_id: str, meeting_ids: list[str]
) -> dict[str, str]:
    """批量取会议标题（任务列表附带关联会议名用），仅限本人会议。"""
    ids = [mid for mid in meeting_ids if mid]
    if not ids:
        return {}
    rows = db.execute(
        select(Meeting.meeting_id, Meeting.title).where(
            Meeting.user_id == user_id, Meeting.meeting_id.in_(ids)
        )
    ).all()
    return {row[0]: row[1] for row in rows}


def card_stats(db: Session, meeting_ids: list[str]) -> dict[str, dict[str, int | bool]]:
    """批量取会议卡片统计（是否有纪要 / 资料 / 录音 / 记录数量），一次查询一张表。"""
    ids = [mid for mid in meeting_ids if mid]
    if not ids:
        return {}
    stats: dict[str, dict[str, int | bool]] = {
        mid: {"has_minutes": False, "material_count": 0, "record_count": 0, "audio_count": 0}
        for mid in ids
    }

    minute_ids = db.execute(
        select(MeetingMinutes.meeting_id).where(MeetingMinutes.meeting_id.in_(ids)).distinct()
    ).scalars()
    for mid in minute_ids:
        stats[mid]["has_minutes"] = True

    for model, key in (
        (MeetingMaterial, "material_count"),
        (MeetingRecord, "record_count"),
        (MeetingAudio, "audio_count"),
    ):
        rows = db.execute(
            select(model.meeting_id, func.count())
            .where(model.meeting_id.in_(ids))
            .group_by(model.meeting_id)
        ).all()
        for mid, count in rows:
            stats[mid][key] = int(count)
    return stats


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
