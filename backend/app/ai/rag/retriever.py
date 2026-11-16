from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.ai.rag.relevance import RelevanceJudge
from app.ai.rag.similarity import cosine
from app.core import metrics
from app.core.config import get_settings
from app.core.exceptions import AppError
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

logger = logging.getLogger(__name__)

# Judge 判定结果计数键：触发量 = true + false + fallback（每次进入 Judge 分支必产其一）
_JUDGE_COUNTER_PREFIX = "rag_judge_total/"
# 阈值告警冷却（key -> 上次触发的 monotonic 时间）
_alert_last_fired: dict[str, float] = {}


def _check_alerts() -> None:
    """窗口 P95 超阈值时打 logger.error 告警行（冷却期内不重复）。

    告警本身异常只记 warning，绝不影响检索主链路。
    """
    settings = get_settings()
    checks = (
        ("total_ms_p95", "retrieval_total_ms", getattr(settings, "rag_alert_total_ms_p95", 3000.0)),
        (
            "candidate_rows_p95",
            "retrieval_candidate_rows",
            getattr(settings, "rag_alert_candidate_rows_p95", 5000.0),
        ),
    )
    now = time.monotonic()
    cooldown = getattr(settings, "rag_alert_cooldown_s", 60.0)
    for key, window_name, threshold in checks:
        if threshold <= 0:
            continue
        p95 = metrics.window_percentile(window_name, 0.95)
        if p95 is None or p95 <= threshold:
            continue
        last_fired = _alert_last_fired.get(key, 0.0)
        if now - last_fired < cooldown:
            continue
        _alert_last_fired[key] = now
        logger.error(
            "RAG 检索性能告警 metric=%s p95=%.1f threshold=%.1f（窗口样本见 GET /api/v1/metrics）",
            window_name,
            p95,
            threshold,
        )


def alert_marks() -> dict[str, float]:
    """告警冷却状态快照（供 `GET /api/v1/metrics` 使用）。"""
    return dict(_alert_last_fired)


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
        self, query: str, results: list[RetrievedChunk], scene: str = "meeting"
    ) -> list[RetrievedChunk]:
        """低分带相关性复核：top1 低于 rag_judge_min_score 时交 LLM Judge 判定。

        判“无关”→ 整体拒答（返回空，拦截分数够但答不了的负样本）；
        Judge 不可用（返回 None）→ 回退分数判定，不阻断检索。
        判定结果计入内存指标（`GET /api/v1/metrics`），日志只记 verdict/score，不记查询原文。
        """
        if not results:
            return results
        settings = get_settings()
        if not settings.rag_judge_enabled:
            return results
        top1_score = results[0].score
        if top1_score >= settings.rag_judge_min_score:
            return results
        if self._judge is None:
            self._judge = self._build_judge(self._config)
        started = time.perf_counter()
        # 对 top3 候选整体判定：任一可作答即保留（避免答案在非 top1 时误拒）
        verdict = self._judge.is_relevant(
            query, [item.excerpt for item in results[:3]]
        )
        elapsed_ms = (time.perf_counter() - started) * 1000
        outcome = "true" if verdict is True else "false" if verdict is False else "fallback"
        metrics.inc_counter(f"{_JUDGE_COUNTER_PREFIX}{outcome}")
        metrics.observe("rag_judge_ms", elapsed_ms)
        logger.info(
            "RAG Judge scene=%s verdict=%s top1_score=%.3f latency_ms=%.1f",
            scene,
            outcome,
            top1_score,
            elapsed_ms,
        )
        if verdict is False:
            return []
        return results

    @staticmethod
    def _observe_and_alert(
        *,
        scope: str,
        candidate_rows: int,
        kept: int,
        sql_ms: float,
        embed_ms: float,
        similarity_ms: float,
        total_ms: float,
        top1_score: float | None,
    ) -> None:
        """记录检索耗时/候选行数指标与结构化日志，并执行阈值告警（不抛异常）。"""
        try:
            metrics.observe("retrieval_sql_ms", sql_ms)
            metrics.observe("retrieval_embed_ms", embed_ms)
            metrics.observe("retrieval_similarity_ms", similarity_ms)
            metrics.observe("retrieval_total_ms", total_ms)
            metrics.observe("retrieval_candidate_rows", float(candidate_rows))
            logger.info(
                "retrieval scope=%s candidate_rows=%d kept=%d "
                "sql_ms=%.1f embed_ms=%.1f similarity_ms=%.1f total_ms=%.1f top1_score=%s",
                scope,
                candidate_rows,
                kept,
                sql_ms,
                embed_ms,
                similarity_ms,
                total_ms,
                "-" if top1_score is None else f"{top1_score:.3f}",
            )
            _check_alerts()
        except Exception as exc:  # noqa: BLE001 —— 埋点失败绝不影响检索主链路
            logger.warning("检索埋点失败（不影响结果）type=%s", type(exc).__name__)

    def _backend(self) -> str:
        """解析生效的检索后端：`auto` 按方言分流，显式值校验方言匹配。

        `python` 为应用层余弦（回滚开关与 SQLite 测试路径）；`pgvector` 走
        SQL ANN（HNSW + 余弦距离）。显式指定 pgvector 但非 PostgreSQL 时报配置错误。
        """
        backend = get_settings().rag_vector_backend
        try:
            dialect = self._db.get_bind().dialect.name
        except Exception:  # noqa: BLE001 —— 方言探测失败按应用层路径兜底
            dialect = ""
        if backend == "auto":
            return "pgvector" if dialect == "postgresql" else "python"
        if backend == "pgvector" and dialect != "postgresql":
            raise AppError(
                "INTERNAL_ERROR",
                "RAG_VECTOR_BACKEND=pgvector 仅支持 PostgreSQL 运行时",
                http_status=500,
                retryable=False,
            )
        return backend

    def _set_hnsw_ef_search(self) -> None:
        """设置 HNSW 查询期 ef_search（事务内局部生效；失败只记 warning）。"""
        ef_search = get_settings().rag_hnsw_ef_search
        if ef_search <= 0:
            return
        try:
            self._db.execute(
                text("SELECT set_config('hnsw.ef_search', :value, true)"),
                {"value": str(ef_search)},
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "设置 hnsw.ef_search 失败（不影响检索）type=%s", type(exc).__name__
            )

    def _finish(
        self,
        query: str,
        *,
        scope: str,
        scored: list[RetrievedChunk],
        top_k: int,
        candidate_rows: int,
        sql_ms: float,
        embed_ms: float,
        similarity_ms: float,
        started: float,
    ) -> list[RetrievedChunk]:
        """排序后的候选统一走 Judge 复核与埋点出口（python/pgvector 共用）。"""
        top1_score = scored[0].score if scored else None
        results = self._apply_judge(query, scored[:top_k], scene=scope)
        self._observe_and_alert(
            scope=scope,
            candidate_rows=candidate_rows,
            kept=len(results),
            sql_ms=sql_ms,
            embed_ms=embed_ms,
            similarity_ms=similarity_ms,
            total_ms=(time.perf_counter() - started) * 1000,
            top1_score=top1_score,
        )
        return results

    def retrieve(
        self,
        query: str,
        *,
        user_id: str,
        scope: str = "current_meeting",
        current_meeting_id: str | None = None,
        top_k: int | None = None,
        min_score: float | None = None,
    ) -> list[RetrievedChunk]:
        settings = get_settings()
        top_k = settings.rag_top_k if top_k is None else top_k
        min_score = settings.rag_min_score if min_score is None else min_score
        if scope == "knowledge_base":
            return self.retrieve_knowledge(
                query,
                user_id=user_id,
                top_k=top_k,
                min_score=min_score,
            )
        if self._backend() == "pgvector":
            return self._retrieve_meeting_pgvector(
                query,
                user_id=user_id,
                current_meeting_id=current_meeting_id,
                top_k=top_k,
                min_score=min_score,
                scope=scope,
            )
        return self._retrieve_meeting_python(
            query,
            user_id=user_id,
            current_meeting_id=current_meeting_id,
            top_k=top_k,
            min_score=min_score,
            scope=scope,
        )

    def _retrieve_meeting_python(
        self,
        query: str,
        *,
        user_id: str,
        current_meeting_id: str | None,
        top_k: int,
        min_score: float,
        scope: str,
    ) -> list[RetrievedChunk]:
        started = time.perf_counter()
        statement = (
            select(DocumentChunk, MeetingMaterial.meeting_id)
            .join(MeetingMaterial, DocumentChunk.material_id == MeetingMaterial.material_id)
            .join(Meeting, MeetingMaterial.meeting_id == Meeting.meeting_id)
            .where(Meeting.user_id == user_id, DocumentChunk.embedding.is_not(None))
        )
        if scope == "current_meeting" and current_meeting_id is not None:
            statement = statement.where(MeetingMaterial.meeting_id == current_meeting_id)
        rows = self._db.execute(statement).all()
        sql_ms = (time.perf_counter() - started) * 1000
        if not rows:
            self._observe_and_alert(
                scope=scope,
                candidate_rows=0,
                kept=0,
                sql_ms=sql_ms,
                embed_ms=0.0,
                similarity_ms=0.0,
                total_ms=(time.perf_counter() - started) * 1000,
                top1_score=None,
            )
            return []

        embed_started = time.perf_counter()
        query_vector = embed_query(query, self._config)
        embed_ms = (time.perf_counter() - embed_started) * 1000
        if not query_vector:
            self._observe_and_alert(
                scope=scope,
                candidate_rows=len(rows),
                kept=0,
                sql_ms=sql_ms,
                embed_ms=embed_ms,
                similarity_ms=0.0,
                total_ms=(time.perf_counter() - started) * 1000,
                top1_score=None,
            )
            return []

        similarity_started = time.perf_counter()
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
        similarity_ms = (time.perf_counter() - similarity_started) * 1000
        top1_score = scored[0].score if scored else None
        results = self._apply_judge(query, scored[:top_k], scene=scope)
        self._observe_and_alert(
            scope=scope,
            candidate_rows=len(rows),
            kept=len(results),
            sql_ms=sql_ms,
            embed_ms=embed_ms,
            similarity_ms=similarity_ms,
            total_ms=(time.perf_counter() - started) * 1000,
            top1_score=top1_score,
        )
        return results

    def retrieve_knowledge(
        self,
        query: str,
        *,
        user_id: str,
        top_k: int | None = None,
        min_score: float | None = None,
    ) -> list[RetrievedChunk]:
        """知识库范围检索（`knowledge_service.search_documents` 与 RAG 共用）。"""
        settings = get_settings()
        top_k = settings.rag_top_k if top_k is None else top_k
        min_score = settings.rag_min_score if min_score is None else min_score
        if self._backend() == "pgvector":
            return self._retrieve_knowledge_pgvector(
                query,
                user_id=user_id,
                top_k=top_k,
                min_score=min_score,
            )
        return self._retrieve_knowledge_python(
            query,
            user_id=user_id,
            top_k=top_k,
            min_score=min_score,
        )

    def _retrieve_knowledge_python(
        self,
        query: str,
        *,
        user_id: str,
        top_k: int,
        min_score: float,
    ) -> list[RetrievedChunk]:
        started = time.perf_counter()
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
        sql_ms = (time.perf_counter() - started) * 1000
        if not rows:
            self._observe_and_alert(
                scope="knowledge_base",
                candidate_rows=0,
                kept=0,
                sql_ms=sql_ms,
                embed_ms=0.0,
                similarity_ms=0.0,
                total_ms=(time.perf_counter() - started) * 1000,
                top1_score=None,
            )
            return []

        embed_started = time.perf_counter()
        query_vector = embed_query(query, self._config)
        embed_ms = (time.perf_counter() - embed_started) * 1000
        if not query_vector:
            self._observe_and_alert(
                scope="knowledge_base",
                candidate_rows=len(rows),
                kept=0,
                sql_ms=sql_ms,
                embed_ms=embed_ms,
                similarity_ms=0.0,
                total_ms=(time.perf_counter() - started) * 1000,
                top1_score=None,
            )
            return []

        similarity_started = time.perf_counter()
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
        similarity_ms = (time.perf_counter() - similarity_started) * 1000
        top1_score = scored[0].score if scored else None
        results = self._apply_judge(query, scored[:top_k], scene="knowledge_base")
        self._observe_and_alert(
            scope="knowledge_base",
            candidate_rows=len(rows),
            kept=len(results),
            sql_ms=sql_ms,
            embed_ms=embed_ms,
            similarity_ms=similarity_ms,
            total_ms=(time.perf_counter() - started) * 1000,
            top1_score=top1_score,
        )
        return results

    def _retrieve_meeting_pgvector(
        self,
        query: str,
        *,
        user_id: str,
        current_meeting_id: str | None,
        top_k: int,
        min_score: float,
        scope: str,
    ) -> list[RetrievedChunk]:
        """PG 路径：HNSW 余弦距离下沉数据库，权限过滤仍在 SQL 前置。

        HNSW + 过滤条件会损失召回，先取 `top_k * rag_ann_oversample` 候选
        （上限 `rag_ann_max_candidates`），再按 `min_score` 过滤并截断 top_k。
        """
        started = time.perf_counter()
        embed_started = time.perf_counter()
        query_vector = embed_query(query, self._config)
        embed_ms = (time.perf_counter() - embed_started) * 1000
        if not query_vector:
            self._observe_and_alert(
                scope=scope,
                candidate_rows=0,
                kept=0,
                sql_ms=0.0,
                embed_ms=embed_ms,
                similarity_ms=0.0,
                total_ms=(time.perf_counter() - started) * 1000,
                top1_score=None,
            )
            return []

        settings = get_settings()
        self._set_hnsw_ef_search()
        distance = DocumentChunk.embedding.cosine_distance(query_vector)
        statement = (
            select(DocumentChunk, MeetingMaterial.meeting_id, distance.label("distance"))
            .join(MeetingMaterial, DocumentChunk.material_id == MeetingMaterial.material_id)
            .join(Meeting, MeetingMaterial.meeting_id == Meeting.meeting_id)
            .where(Meeting.user_id == user_id, DocumentChunk.embedding.is_not(None))
            .order_by(distance)
            .limit(
                min(
                    max(top_k, 1) * settings.rag_ann_oversample,
                    settings.rag_ann_max_candidates,
                )
            )
        )
        if scope == "current_meeting" and current_meeting_id is not None:
            statement = statement.where(MeetingMaterial.meeting_id == current_meeting_id)

        sql_started = time.perf_counter()
        rows = self._db.execute(statement).all()
        sql_ms = (time.perf_counter() - sql_started) * 1000
        if not rows:
            self._observe_and_alert(
                scope=scope,
                candidate_rows=0,
                kept=0,
                sql_ms=sql_ms,
                embed_ms=embed_ms,
                similarity_ms=0.0,
                total_ms=(time.perf_counter() - started) * 1000,
                top1_score=None,
            )
            return []

        similarity_started = time.perf_counter()
        scored: list[RetrievedChunk] = []
        for chunk, meeting_id, distance_value in rows:
            # pgvector 余弦距离 `<=>` = 1 - 余弦相似度，换算回相似度保持 score 口径
            score = 1.0 - float(distance_value)
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
        similarity_ms = (time.perf_counter() - similarity_started) * 1000
        return self._finish(
            query,
            scope=scope,
            scored=scored,
            top_k=top_k,
            candidate_rows=len(rows),
            sql_ms=sql_ms,
            embed_ms=embed_ms,
            similarity_ms=similarity_ms,
            started=started,
        )

    def _retrieve_knowledge_pgvector(
        self,
        query: str,
        *,
        user_id: str,
        top_k: int,
        min_score: float,
    ) -> list[RetrievedChunk]:
        """知识库 PG 路径：与会议材料同构，按 `knowledge_documents.user_id` 前置过滤。"""
        started = time.perf_counter()
        embed_started = time.perf_counter()
        query_vector = embed_query(query, self._config)
        embed_ms = (time.perf_counter() - embed_started) * 1000
        if not query_vector:
            self._observe_and_alert(
                scope="knowledge_base",
                candidate_rows=0,
                kept=0,
                sql_ms=0.0,
                embed_ms=embed_ms,
                similarity_ms=0.0,
                total_ms=(time.perf_counter() - started) * 1000,
                top1_score=None,
            )
            return []

        settings = get_settings()
        self._set_hnsw_ef_search()
        distance = KnowledgeChunk.embedding.cosine_distance(query_vector)
        statement = (
            select(
                KnowledgeChunk, KnowledgeDocument.file_name, distance.label("distance")
            )
            .join(
                KnowledgeDocument,
                KnowledgeChunk.document_id == KnowledgeDocument.document_id,
            )
            .where(
                KnowledgeDocument.user_id == user_id,
                KnowledgeChunk.embedding.is_not(None),
            )
            .order_by(distance)
            .limit(
                min(
                    max(top_k, 1) * settings.rag_ann_oversample,
                    settings.rag_ann_max_candidates,
                )
            )
        )
        sql_started = time.perf_counter()
        rows = self._db.execute(statement).all()
        sql_ms = (time.perf_counter() - sql_started) * 1000
        if not rows:
            self._observe_and_alert(
                scope="knowledge_base",
                candidate_rows=0,
                kept=0,
                sql_ms=sql_ms,
                embed_ms=embed_ms,
                similarity_ms=0.0,
                total_ms=(time.perf_counter() - started) * 1000,
                top1_score=None,
            )
            return []

        similarity_started = time.perf_counter()
        scored: list[RetrievedChunk] = []
        for chunk, file_name, distance_value in rows:
            score = 1.0 - float(distance_value)
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
        similarity_ms = (time.perf_counter() - similarity_started) * 1000
        return self._finish(
            query,
            scope="knowledge_base",
            scored=scored,
            top_k=top_k,
            candidate_rows=len(rows),
            sql_ms=sql_ms,
            embed_ms=embed_ms,
            similarity_ms=similarity_ms,
            started=started,
        )
