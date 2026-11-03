from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.rag.relevance import RelevanceJudge
from app.ai.rag.similarity import cosine
from app.core.config import get_settings
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
        self._judge: RelevanceJudge | None = None

    @staticmethod
    def _build_judge(config: ModelConfig) -> RelevanceJudge:
        """Judge 构造工厂（测试可 monkeypatch）。"""
        return RelevanceJudge(config)

    def _apply_judge(
        self, query: str, results: list[RetrievedChunk]
    ) -> list[RetrievedChunk]:
        """低分带相关性复核：top1 低于 rag_judge_min_score 时交 LLM Judge 判定。

        判“无关”→ 整体拒答（返回空，拦截分数够但答不了的负样本）；
        Judge 不可用（返回 None）→ 回退分数判定，不阻断检索。
        """
        if not results:
            return results
        settings = get_settings()
        if not settings.rag_judge_enabled:
            return results
        if results[0].score >= settings.rag_judge_min_score:
            return results
        if self._judge is None:
            self._judge = self._build_judge(self._config)
        # 对 top3 候选整体判定：任一可作答即保留（避免答案在非 top1 时误拒）
        verdict = self._judge.is_relevant(
            query, [item.excerpt for item in results[:3]]
        )
        if verdict is False:
            return []
        return results

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
            return self.retrieve_knowledge(
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
        return self._apply_judge(query, scored[:top_k])

    def retrieve_knowledge(
        self,
        query: str,
        *,
        user_id: str,
        top_k: int = 5,
        min_score: float = 0.3,
    ) -> list[RetrievedChunk]:
        """知识库范围检索（`knowledge_service.search_documents` 与 RAG 共用）。"""
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
        return self._apply_judge(query, scored[:top_k])
