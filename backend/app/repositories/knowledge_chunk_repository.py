from __future__ import annotations

from sqlalchemy import delete as sa_delete
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.knowledge_chunk import KnowledgeChunk
from app.utils.ids import new_id


def delete_by_document(db: Session, document_id: str) -> None:
    db.execute(
        sa_delete(KnowledgeChunk).where(KnowledgeChunk.document_id == document_id)
    )


def count_by_document(db: Session, document_id: str) -> int:
    return int(
        db.execute(
            select(func.count())
            .select_from(KnowledgeChunk)
            .where(KnowledgeChunk.document_id == document_id)
        ).scalar_one()
    )


def copy_by_document(
    db: Session, source_document_id: str, target_document_id: str
) -> int:
    """增量索引复用：把源文档分块复制到目标文档（新 chunk_id，内容与向量原样）。

    返回复制的分块数；调用方负责事务提交。
    """
    rows = list(
        db.execute(
            select(KnowledgeChunk)
            .where(KnowledgeChunk.document_id == source_document_id)
            .order_by(KnowledgeChunk.chunk_index.asc())
        ).scalars().all()
    )
    for row in rows:
        db.add(
            KnowledgeChunk(
                chunk_id=new_id("kchk"),
                document_id=target_document_id,
                content=row.content,
                chunk_index=row.chunk_index,
                embedding=row.embedding,
            )
        )
    return len(rows)
