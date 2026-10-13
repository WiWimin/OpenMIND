from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.action_item import ActionItem
from app.models.meeting import Meeting


def create(
    db: Session,
    *,
    action_id: str,
    meeting_id: str,
    content: str,
    assignee: str | None,
    due_date: date | None,
    source_record_id: str | None,
    source_excerpt: str | None,
    status: str = "pending_confirmation",
) -> ActionItem:
    item = ActionItem(
        action_id=action_id,
        meeting_id=meeting_id,
        content=content,
        assignee=assignee,
        due_date=due_date,
        source_record_id=source_record_id,
        source_excerpt=source_excerpt,
        status=status,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def get_owned(db: Session, action_id: str, user_id: str) -> ActionItem | None:
    statement = (
        select(ActionItem)
        .join(Meeting, ActionItem.meeting_id == Meeting.meeting_id)
        .where(ActionItem.action_id == action_id, Meeting.user_id == user_id)
    )
    return db.execute(statement).scalar_one_or_none()


def list_by_meeting(
    db: Session, meeting_id: str, *, limit: int, offset: int
) -> list[ActionItem]:
    statement = (
        select(ActionItem)
        .where(ActionItem.meeting_id == meeting_id)
        .order_by(ActionItem.created_at.asc())
        .limit(limit)
        .offset(offset)
    )
    return list(db.execute(statement).scalars().all())


def count_by_meeting(db: Session, meeting_id: str) -> int:
    statement = (
        select(func.count())
        .select_from(ActionItem)
        .where(ActionItem.meeting_id == meeting_id)
    )
    return int(db.execute(statement).scalar_one())


def update(db: Session, item: ActionItem) -> ActionItem:
    db.commit()
    db.refresh(item)
    return item


def delete(db: Session, item: ActionItem) -> None:
    db.delete(item)
    db.commit()
