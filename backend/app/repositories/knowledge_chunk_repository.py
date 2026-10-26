from __future__ import annotations

from sqlalchemy import delete as sa_delete
from sqlalchemy.orm import Session

from app.models.knowledge_chunk import KnowledgeChunk


def delete_by_document(db: Session, document_id: str) -> None:
    db.execute(
        sa_delete(KnowledgeChunk).where(KnowledgeChunk.document_id == document_id)
    )
