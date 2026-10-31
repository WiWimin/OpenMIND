from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.meeting_template import MeetingTemplate


def create(
    db: Session,
    *,
    template_id: str,
    user_id: str,
    name: str,
    description: str | None,
    file_name: str,
    storage_key: str,
    content_text: str,
) -> MeetingTemplate:
    template = MeetingTemplate(
        template_id=template_id,
        user_id=user_id,
        name=name,
        description=description,
        file_name=file_name,
        storage_key=storage_key,
        content_text=content_text,
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


def get_owned(db: Session, template_id: str, user_id: str) -> MeetingTemplate | None:
    return db.execute(
        select(MeetingTemplate).where(
            MeetingTemplate.template_id == template_id,
            MeetingTemplate.user_id == user_id,
        )
    ).scalar_one_or_none()


def list_by_user(db: Session, user_id: str) -> list[MeetingTemplate]:
    statement = (
        select(MeetingTemplate)
        .where(MeetingTemplate.user_id == user_id)
        .order_by(MeetingTemplate.created_at.desc())
    )
    return list(db.execute(statement).scalars().all())


def count_by_user(db: Session, user_id: str) -> int:
    statement = (
        select(func.count())
        .select_from(MeetingTemplate)
        .where(MeetingTemplate.user_id == user_id)
    )
    return int(db.execute(statement).scalar_one())


def delete(db: Session, template: MeetingTemplate) -> None:
    db.delete(template)
    db.commit()
