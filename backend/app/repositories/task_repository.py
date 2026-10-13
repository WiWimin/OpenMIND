from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.task import PersonalTask


def create(
    db: Session,
    *,
    task_id: str,
    user_id: str,
    meeting_id: str | None,
    action_id: str | None,
    title: str,
    due_date: date | None,
    status: str = "todo",
) -> PersonalTask:
    task = PersonalTask(
        task_id=task_id,
        user_id=user_id,
        meeting_id=meeting_id,
        action_id=action_id,
        title=title,
        due_date=due_date,
        status=status,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def get_owned(db: Session, task_id: str, user_id: str) -> PersonalTask | None:
    return db.execute(
        select(PersonalTask).where(
            PersonalTask.task_id == task_id,
            PersonalTask.user_id == user_id,
        )
    ).scalar_one_or_none()


def get_by_action(db: Session, action_id: str) -> PersonalTask | None:
    return db.execute(
        select(PersonalTask).where(PersonalTask.action_id == action_id)
    ).scalar_one_or_none()


def list_by_user(
    db: Session, user_id: str, *, status: str | None, limit: int, offset: int
) -> list[PersonalTask]:
    statement = select(PersonalTask).where(PersonalTask.user_id == user_id)
    if status is not None:
        statement = statement.where(PersonalTask.status == status)
    statement = statement.order_by(PersonalTask.created_at.desc()).limit(limit).offset(offset)
    return list(db.execute(statement).scalars().all())


def count_by_user(db: Session, user_id: str, *, status: str | None) -> int:
    statement = (
        select(func.count()).select_from(PersonalTask).where(PersonalTask.user_id == user_id)
    )
    if status is not None:
        statement = statement.where(PersonalTask.status == status)
    return int(db.execute(statement).scalar_one())


def update(db: Session, task: PersonalTask) -> PersonalTask:
    db.commit()
    db.refresh(task)
    return task
