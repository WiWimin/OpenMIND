from __future__ import annotations

from sqlalchemy import delete as sa_delete
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.chunk import DocumentChunk
from app.models.material import MeetingMaterial


def delete_by_material(db: Session, material_id: str) -> None:
    db.execute(sa_delete(DocumentChunk).where(DocumentChunk.material_id == material_id))


def delete_by_meeting(db: Session, meeting_id: str) -> None:
    material_ids = select(MeetingMaterial.material_id).where(
        MeetingMaterial.meeting_id == meeting_id
    )
    db.execute(sa_delete(DocumentChunk).where(DocumentChunk.material_id.in_(material_ids)))
