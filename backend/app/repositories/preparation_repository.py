from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.meeting import Meeting
from app.models.preparation import Preparation


def create(
    db: Session,
    *,
    preparation_id: str,
    meeting_id: str,
    summary: str,
    checklist: list[str],
    status: str = "draft",
) -> Preparation:
    preparation = Preparation(
        preparation_id=preparation_id,
        meeting_id=meeting_id,
        summary=summary,
        checklist=checklist,
        status=status,
    )
    db.add(preparation)
    db.commit()
    db.refresh(preparation)
    return preparation


def get_owned(db: Session, preparation_id: str, user_id: str) -> Preparation | None:
    statement = (
        select(Preparation)
        .join(Meeting, Preparation.meeting_id == Meeting.meeting_id)
        .where(
            Preparation.preparation_id == preparation_id,
            Meeting.user_id == user_id,
        )
    )
    return db.execute(statement).scalar_one_or_none()


def list_by_meeting(
    db: Session, meeting_id: str, *, limit: int, offset: int
) -> list[Preparation]:
    statement = (
        select(Preparation)
        .where(Preparation.meeting_id == meeting_id)
        .order_by(Preparation.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(db.execute(statement).scalars().all())


def count_by_meeting(db: Session, meeting_id: str) -> int:
    statement = (
        select(func.count())
        .select_from(Preparation)
        .where(Preparation.meeting_id == meeting_id)
    )
    return int(db.execute(statement).scalar_one())


def update(db: Session, preparation: Preparation) -> Preparation:
    db.commit()
    db.refresh(preparation)
    return preparation
