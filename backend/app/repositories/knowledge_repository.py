from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.knowledge_document import KnowledgeDocument


def create(
    db: Session,
    *,
    document_id: str,
    user_id: str,
    file_name: str,
    document_type: str,
    storage_key: str,
) -> KnowledgeDocument:
    document = KnowledgeDocument(
        document_id=document_id,
        user_id=user_id,
        file_name=file_name,
        type=document_type,
        storage_key=storage_key,
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def get_owned(db: Session, document_id: str, user_id: str) -> KnowledgeDocument | None:
    return db.execute(
        select(KnowledgeDocument).where(
            KnowledgeDocument.document_id == document_id,
            KnowledgeDocument.user_id == user_id,
        )
    ).scalar_one_or_none()


def find_reusable_index(
    db: Session,
    *,
    user_id: str,
    content_hash: str,
    fingerprint: str,
    exclude_document_id: str,
) -> KnowledgeDocument | None:
    """增量索引复用源：同用户、同内容、同指纹且已成功建索引的知识库文档。

    仅限本表（知识库）内复用，不跨到会议材料库，避免跨库脏召回；
    `index_fingerprint` 为空的存量行永不命中（旧向量产出参数未知）。
    """
    statement = (
        select(KnowledgeDocument)
        .where(
            KnowledgeDocument.user_id == user_id,
            KnowledgeDocument.content_hash == content_hash,
            KnowledgeDocument.index_fingerprint == fingerprint,
            KnowledgeDocument.processing_status == "processed",
            KnowledgeDocument.document_id != exclude_document_id,
            KnowledgeDocument.content.is_not(None),
        )
        .order_by(KnowledgeDocument.created_at.asc())
        .limit(1)
    )
    return db.execute(statement).scalar_one_or_none()


def list_by_user(
    db: Session, user_id: str, *, limit: int, offset: int
) -> list[KnowledgeDocument]:
    statement = (
        select(KnowledgeDocument)
        .where(KnowledgeDocument.user_id == user_id)
        .order_by(KnowledgeDocument.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(db.execute(statement).scalars().all())


def count_by_user(db: Session, user_id: str) -> int:
    statement = (
        select(func.count())
        .select_from(KnowledgeDocument)
        .where(KnowledgeDocument.user_id == user_id)
    )
    return int(db.execute(statement).scalar_one())


def delete(db: Session, document: KnowledgeDocument) -> None:
    db.delete(document)
    db.commit()
