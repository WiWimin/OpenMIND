from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.rag.similarity import cosine
from app.models.chunk import DocumentChunk
from app.models.knowledge_chunk import KnowledgeChunk
from app.models.knowledge_document import KnowledgeDocument
from app.models.material import MeetingMaterial
from app.models.meeting import Meeting
from app.services.model_config_service import (
    ModelConfig,
    build_embedding_client,
    resolve_model_config,
)


@dataclass(frozen=True)
class RetrievedChunk:
    meeting_id: str | None
    material_id: str | None
    record_id: str | None
    excerpt: str
    score: float
    document_id: str | None = None
    document_name: str | None = None


def embed_query(text: str, config: ModelConfig) -> list[float]:
    vectors = build_embedding_client(config).embed([text])
    return [float(value) for value in vectors[0]] if vectors else []


class VectorRetriever:
    """按当前用户权限范围检索文档分块（余弦相似度）。

    先在 SQL 中按 `meetings.user_id` 限定范围，再计算相似度——不做全库检索后过滤。
    待数据量增大后可由 pgvector 索引（HNSW/IVFFlat）替换本实现的相似度计算。
    """

    def __init__(self, db: Session, user_id: str) -> None:
        self._db = db
        self._user_id = user_id
        self._config = resolve_model_config(db, user_id)

    def retrieve(
        self,
        query: str,
        *,
        user_id: str,
        scope: str = "current_meeting",
        current_meeting_id: str | None = None,
        top_k: int = 5,
        min_score: float = 0.3,
    ) -> list[RetrievedChunk]:
        if scope == "knowledge_base":
            return self._retrieve_knowledge(
                query,
                user_id=user_id,
                top_k=top_k,
                min_score=min_score,
            )

        statement = (
            select(DocumentChunk, MeetingMaterial.meeting_id)
            .join(MeetingMaterial, DocumentChunk.material_id == MeetingMaterial.material_id)
            .join(Meeting, MeetingMaterial.meeting_id == Meeting.meeting_id)
            .where(Meeting.user_id == user_id, DocumentChunk.embedding.is_not(None))
        )
        if scope == "current_meeting" and current_meeting_id is not None:
            statement = statement.where(MeetingMaterial.meeting_id == current_meeting_id)
        rows = self._db.execute(statement).all()
        if not rows:
            return []

        query_vector = embed_query(query, self._config)
        if not query_vector:
            return []

        scored: list[RetrievedChunk] = []
        for chunk, meeting_id in rows:
            score = cosine(query_vector, [float(value) for value in chunk.embedding])
            if score >= min_score:
                scored.append(
                    RetrievedChunk(
                        meeting_id=meeting_id,
                        material_id=chunk.material_id,
                        record_id=None,
                        excerpt=chunk.content,
                        score=score,
                    )
                )
        scored.sort(key=lambda item: item.score, reverse=True)
        return scored[:top_k]

    def _retrieve_knowledge(
        self,
        query: str,
        *,
        user_id: str,
        top_k: int,
        min_score: float,
    ) -> list[RetrievedChunk]:
        statement = (
            select(KnowledgeChunk, KnowledgeDocument.file_name)
            .join(
                KnowledgeDocument,
                KnowledgeChunk.document_id == KnowledgeDocument.document_id,
            )
            .where(
                KnowledgeDocument.user_id == user_id,
                KnowledgeChunk.embedding.is_not(None),
            )
        )
        rows = self._db.execute(statement).all()
        if not rows:
            return []

        query_vector = embed_query(query, self._config)
        if not query_vector:
            return []

        scored: list[RetrievedChunk] = []
        for chunk, file_name in rows:
            score = cosine(query_vector, [float(value) for value in chunk.embedding])
            if score >= min_score:
                scored.append(
                    RetrievedChunk(
                        meeting_id=None,
                        material_id=None,
                        record_id=None,
                        excerpt=chunk.content,
                        score=score,
                        document_id=chunk.document_id,
                        document_name=file_name,
                    )
                )
        scored.sort(key=lambda item: item.score, reverse=True)
        return scored[:top_k]
