from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.audio import MeetingAudio


def create(
    db: Session,
    *,
    audio_id: str,
    meeting_id: str,
    user_id: str,
    file_name: str,
    audio_type: str,
    storage_key: str,
) -> MeetingAudio:
    audio = MeetingAudio(
        audio_id=audio_id,
        meeting_id=meeting_id,
        user_id=user_id,
        file_name=file_name,
        type=audio_type,
        storage_key=storage_key,
    )
    db.add(audio)
    db.commit()
    db.refresh(audio)
    return audio


def get_owned(db: Session, audio_id: str, user_id: str) -> MeetingAudio | None:
    return db.execute(
        select(MeetingAudio).where(
            MeetingAudio.audio_id == audio_id,
            MeetingAudio.user_id == user_id,
        )
    ).scalar_one_or_none()


def list_by_meeting(
    db: Session, meeting_id: str, *, limit: int, offset: int
) -> list[MeetingAudio]:
    statement = (
        select(MeetingAudio)
        .where(MeetingAudio.meeting_id == meeting_id)
        .order_by(MeetingAudio.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(db.execute(statement).scalars().all())


def count_by_meeting(db: Session, meeting_id: str) -> int:
    statement = (
        select(func.count())
        .select_from(MeetingAudio)
        .where(MeetingAudio.meeting_id == meeting_id)
    )
    return int(db.execute(statement).scalar_one())


def update(db: Session, audio: MeetingAudio) -> MeetingAudio:
    db.commit()
    db.refresh(audio)
    return audio


def delete(db: Session, audio: MeetingAudio) -> None:
    db.delete(audio)
    db.commit()
