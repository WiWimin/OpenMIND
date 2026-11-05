"""RAG 可观测性：Judge 判定埋点、检索计时拆分与阈值告警。"""

from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest
from sqlalchemy.orm import Session

from app.ai.rag import retriever as rag
from app.core import metrics
from app.models.chunk import DocumentChunk
from app.repositories import (
    material_repository,
    meeting_repository,
    user_repository,
)

# 查询向量 [1,0] 与分块向量 [0.5, 0.866] 的余弦 = 0.5 → 低分带（触发 Judge）
_LOW_SCORE_EMBEDDING = [0.5, 0.8660254]


def _seed_chunk(db: Session, name: str, embedding: list[float]) -> str:
    user = user_repository.create(db, user_id=f"usr_{name}", name=name, password_hash="x")
    meeting_repository.create(
        db,
        meeting_id=f"mtg_{name}",
        user_id=user.user_id,
        title="周会",
        topic=None,
        meeting_time=None,
    )
    material_repository.create(
        db,
        material_id=f"mat_{name}",
        meeting_id=f"mtg_{name}",
        user_id=user.user_id,
        file_name="a.txt",
        material_type="txt",
        source=None,
        storage_key=f"materials/mat_{name}.txt",
    )
    db.add(
        DocumentChunk(
            chunk_id=f"chk_{name}",
            material_id=f"mat_{name}",
            content="内容",
            chunk_index=0,
            embedding=embedding,
        )
    )
    db.commit()
    return user.user_id


class _FakeJudge:
    def __init__(self, verdict: bool | None) -> None:
        self.verdict = verdict

    def is_relevant(self, query: str, excerpts: list[str]) -> bool | None:
        return self.verdict


def _patch_env(
    monkeypatch: pytest.MonkeyPatch,
    *,
    judge_enabled: bool = True,
    alert_threshold: float = -1.0,  # 默认关闭告警，聚焦计数
) -> None:
    monkeypatch.setattr(
        rag,
        "get_settings",
        lambda: SimpleNamespace(
            rag_judge_enabled=judge_enabled,
            rag_judge_min_score=0.6,
            rag_alert_total_ms_p95=alert_threshold,
            rag_alert_candidate_rows_p95=-1.0,
            rag_alert_cooldown_s=60.0,
        ),
    )
    monkeypatch.setattr(rag, "embed_query", lambda text, config: [1.0, 0.0])
    monkeypatch.setattr(rag, "_alert_last_fired", {})


def _patch_judge(monkeypatch: pytest.MonkeyPatch, verdict: bool | None) -> None:
    fake = _FakeJudge(verdict)
    monkeypatch.setattr(
        rag.VectorRetriever,
        "_build_judge",
        staticmethod(lambda config: fake),
    )


def _retrieve(db: Session, user_id: str) -> list:
    return rag.VectorRetriever(db, user_id).retrieve(
        "问题", user_id=user_id, scope="current_meeting"
    )


# ---------- Judge 埋点 ----------


def test_judge_counter_true(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    user_id = _seed_chunk(db_session, "obs-a", _LOW_SCORE_EMBEDDING)
    _patch_env(monkeypatch)
    _patch_judge(monkeypatch, verdict=True)

    _retrieve(db_session, user_id)

    counters = metrics.snapshot()["counters"]
    assert counters["rag_judge_total/true"] == 1
    assert "rag_judge_total/false" not in counters
    assert "rag_judge_total/fallback" not in counters


def test_judge_counter_false(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    user_id = _seed_chunk(db_session, "obs-b", _LOW_SCORE_EMBEDDING)
    _patch_env(monkeypatch)
    _patch_judge(monkeypatch, verdict=False)

    results = _retrieve(db_session, user_id)

    assert results == []  # 判无关 → 整体拒答
    counters = metrics.snapshot()["counters"]
    assert counters["rag_judge_total/false"] == 1
    assert "rag_judge_total/true" not in counters


def test_judge_counter_fallback(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    user_id = _seed_chunk(db_session, "obs-c", _LOW_SCORE_EMBEDDING)
    _patch_env(monkeypatch)
    _patch_judge(monkeypatch, verdict=None)

    _retrieve(db_session, user_id)

    counters = metrics.snapshot()["counters"]
    assert counters["rag_judge_total/fallback"] == 1


def test_judge_high_score_not_counted(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """高分带不触达 Judge，也不产生任何判定计数（触发量口径 = 实际调 LLM）。"""
    user_id = _seed_chunk(db_session, "obs-d", [1.0, 0.0])
    _patch_env(monkeypatch)
    monkeypatch.setattr(
        rag.VectorRetriever,
        "_build_judge",
        staticmethod(lambda config: pytest.fail("高分带不应构造 Judge")),
    )

    _retrieve(db_session, user_id)

    counters = metrics.snapshot()["counters"]
    assert not any(key.startswith("rag_judge_total/") for key in counters)


def test_judge_disabled_not_counted(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    user_id = _seed_chunk(db_session, "obs-e", _LOW_SCORE_EMBEDDING)
    _patch_env(monkeypatch, judge_enabled=False)
    monkeypatch.setattr(
        rag.VectorRetriever,
        "_build_judge",
        staticmethod(lambda config: pytest.fail("Judge 已禁用不应构造")),
    )

    _retrieve(db_session, user_id)

    counters = metrics.snapshot()["counters"]
    assert not any(key.startswith("rag_judge_total/") for key in counters)


# ---------- 检索计时与候选行数 ----------


def test_retrieval_windows_populated(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    user_id = _seed_chunk(db_session, "obs-f", [1.0, 0.0])
    _patch_env(monkeypatch)  # 高分带，不触发 Judge

    _retrieve(db_session, user_id)

    windows = metrics.snapshot()["windows"]
    assert windows["retrieval_candidate_rows"]["samples"] == 1
    assert windows["retrieval_candidate_rows"]["max"] == 1.0
    assert windows["retrieval_total_ms"]["samples"] >= 1
    assert windows["retrieval_sql_ms"]["samples"] >= 1
    assert windows["retrieval_embed_ms"]["samples"] >= 1
    assert windows["retrieval_similarity_ms"]["samples"] >= 1
    # 未触发 Judge 的场景不应产生 Judge 耗时样本
    assert "rag_judge_ms" not in windows


def test_retrieval_logged_as_structured_line(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    user_id = _seed_chunk(db_session, "obs-g", [1.0, 0.0])
    _patch_env(monkeypatch)

    with caplog.at_level(logging.INFO, logger="app.ai.rag.retriever"):
        _retrieve(db_session, user_id)

    lines = "\n".join(record.getMessage() for record in caplog.records)
    assert "retrieval scope=current_meeting candidate_rows=1" in lines
    assert "similarity_ms=" in lines
    # 日志不含查询原文（本用例查询为「问题」，只断言字段名而非内容）
    assert "问题" not in lines.split("retrieval scope=")[0]


def test_retrieval_observability_failure_never_breaks_retrieval(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """埋点异常只告警，不阻断检索主链路。"""
    user_id = _seed_chunk(db_session, "obs-h", [1.0, 0.0])
    _patch_env(monkeypatch)
    monkeypatch.setattr(
        metrics, "observe", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom"))
    )

    results = _retrieve(db_session, user_id)

    assert len(results) == 1


# ---------- 阈值告警 ----------


def test_alert_fires_when_p95_exceeds_threshold(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    user_id = _seed_chunk(db_session, "obs-i", [1.0, 0.0])
    _patch_env(monkeypatch, alert_threshold=0.5)  # 窗口 p95=5ms > 0.5ms → 告警
    # 窗口样本 ≥20 才会产出 p95
    for _ in range(20):
        metrics.observe("retrieval_total_ms", 5.0)

    with caplog.at_level(logging.ERROR, logger="app.ai.rag.retriever"):
        _retrieve(db_session, user_id)

    errors = [
        record.getMessage()
        for record in caplog.records
        if record.levelno >= logging.ERROR
    ]
    assert any("RAG 检索性能告警" in line for line in errors)


def test_alert_respects_cooldown(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    user_id = _seed_chunk(db_session, "obs-j", [1.0, 0.0])
    _patch_env(monkeypatch, alert_threshold=0.5)
    for _ in range(20):
        metrics.observe("retrieval_total_ms", 5.0)

    with caplog.at_level(logging.ERROR, logger="app.ai.rag.retriever"):
        _retrieve(db_session, user_id)
        _retrieve(db_session, user_id)

    errors = [
        record.getMessage()
        for record in caplog.records
        if record.levelno >= logging.ERROR and "RAG 检索性能告警" in record.getMessage()
    ]
    assert len(errors) == 1  # 冷却期内第二次不重复告警


def test_alert_disabled_when_threshold_non_positive(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    user_id = _seed_chunk(db_session, "obs-k", [1.0, 0.0])
    _patch_env(monkeypatch, alert_threshold=-1.0)
    for _ in range(20):
        metrics.observe("retrieval_total_ms", 99999.0)

    with caplog.at_level(logging.ERROR, logger="app.ai.rag.retriever"):
        _retrieve(db_session, user_id)

    assert not any("RAG 检索性能告警" in record.getMessage() for record in caplog.records)


# ---------- 指标端点 ----------


def test_metrics_endpoint_exposes_judge_and_windows(client) -> None:
    from app.core import metrics as m

    m.inc_counter("rag_judge_total/true")
    m.inc_counter("rag_judge_total/false")
    m.inc_counter("rag_judge_total/fallback")
    for _ in range(30):
        m.observe("retrieval_total_ms", 10.0)

    response = client.get("/api/v1/metrics")

    assert response.status_code == 200
    data = response.json()
    judge = data["rag_judge"]
    assert judge["triggered"] == 3
    assert judge["true"] == 1
    assert judge["false"] == 1
    assert judge["fallback"] == 1
    assert judge["ratios"]["true"] == pytest.approx(1 / 3, abs=1e-3)
    assert data["windows"]["retrieval_total_ms"]["p95"] == 10.0
    assert data["windows"]["retrieval_total_ms"]["insufficient"] is False
    assert "alerts" in data
