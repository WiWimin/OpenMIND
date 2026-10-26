from __future__ import annotations

from sqlalchemy import delete as sa_delete
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.material import MeetingMaterial


def create(
    db: Session,
    *,
    material_id: str,
    meeting_id: str,
    user_id: str,
    file_name: str,
    material_type: str,
    source: str | None,
    storage_key: str,
) -> MeetingMaterial:
    material = MeetingMaterial(
        material_id=material_id,
        meeting_id=meeting_id,
        user_id=user_id,
        file_name=file_name,
        type=material_type,
        source=source,
        storage_key=storage_key,
    )
    db.add(material)
    db.commit()
    db.refresh(material)
    return material


def get_owned(db: Session, material_id: str, user_id: str) -> MeetingMaterial | None:
    return db.execute(
        select(MeetingMaterial).where(
            MeetingMaterial.material_id == material_id,
            MeetingMaterial.user_id == user_id,
        )
    ).scalar_one_or_none()


def list_by_meeting(
    db: Session, meeting_id: str, *, limit: int, offset: int
) -> list[MeetingMaterial]:
    statement = (
        select(MeetingMaterial)
        .where(MeetingMaterial.meeting_id == meeting_id)
        .order_by(MeetingMaterial.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(db.execute(statement).scalars().all())


def count_by_meeting(db: Session, meeting_id: str) -> int:
    statement = (
        select(func.count())
        .select_from(MeetingMaterial)
        .where(MeetingMaterial.meeting_id == meeting_id)
    )
    return int(db.execute(statement).scalar_one())


def list_contents(db: Session, meeting_id: str) -> list[str]:
    statement = (
        select(MeetingMaterial.content)
        .where(
            MeetingMaterial.meeting_id == meeting_id,
            MeetingMaterial.content.is_not(None),
        )
        .order_by(MeetingMaterial.created_at.asc())
    )
    return [content for content in db.execute(statement).scalars().all() if content]


def delete(db: Session, material: MeetingMaterial) -> None:
    db.delete(material)
    db.commit()


def list_content_rows(
    db: Session, user_id: str, *, meeting_id: str | None = None
) -> list[MeetingMaterial]:
    statement = select(MeetingMaterial).where(
        MeetingMaterial.user_id == user_id,
        MeetingMaterial.content.is_not(None),
    )
    if meeting_id is not None:
        statement = statement.where(MeetingMaterial.meeting_id == meeting_id)
    statement = statement.order_by(MeetingMaterial.created_at.asc())
    return list(db.execute(statement).scalars().all())


def list_all_by_meeting(db: Session, meeting_id: str) -> list[MeetingMaterial]:
    statement = (
        select(MeetingMaterial)
        .where(MeetingMaterial.meeting_id == meeting_id)
        .order_by(MeetingMaterial.created_at.asc())
    )
    return list(db.execute(statement).scalars().all())


def delete_by_meeting(db: Session, meeting_id: str) -> None:
    db.execute(sa_delete(MeetingMaterial).where(MeetingMaterial.meeting_id == meeting_id))
