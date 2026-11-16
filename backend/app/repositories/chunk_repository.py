from __future__ import annotations

from sqlalchemy import delete as sa_delete
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.chunk import DocumentChunk
from app.models.material import MeetingMaterial
from app.utils.ids import new_id


def delete_by_material(db: Session, material_id: str) -> None:
    db.execute(sa_delete(DocumentChunk).where(DocumentChunk.material_id == material_id))


def delete_by_meeting(db: Session, meeting_id: str) -> None:
    material_ids = select(MeetingMaterial.material_id).where(
        MeetingMaterial.meeting_id == meeting_id
    )
    db.execute(sa_delete(DocumentChunk).where(DocumentChunk.material_id.in_(material_ids)))


def count_by_material(db: Session, material_id: str) -> int:
    return int(
        db.execute(
            select(func.count())
            .select_from(DocumentChunk)
            .where(DocumentChunk.material_id == material_id)
        ).scalar_one()
    )


def copy_by_material(
    db: Session, source_material_id: str, target_material_id: str
) -> int:
    """增量索引复用：把源材料分块复制到目标材料（新 chunk_id，内容与向量原样）。

    返回复制的分块数；调用方负责事务提交。
    """
    rows = list(
        db.execute(
            select(DocumentChunk)
            .where(DocumentChunk.material_id == source_material_id)
            .order_by(DocumentChunk.chunk_index.asc())
        ).scalars().all()
    )
    for row in rows:
        db.add(
            DocumentChunk(
                chunk_id=new_id("chk"),
                material_id=target_material_id,
                content=row.content,
                chunk_index=row.chunk_index,
                embedding=row.embedding,
            )
        )
    return len(rows)
