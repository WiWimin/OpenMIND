"""PostgreSQL + pgvector 集成测试：HNSW 索引与 SQL ANN 检索。

仅在设置 `TEST_DATABASE_URL`（指向 PostgreSQL + pgvector）时执行，
CI 与本地默认走 SQLite 单测，无需 PostgreSQL。

运行：
    TEST_DATABASE_URL=postgresql+psycopg://openmind:change-me@localhost:5432/openmind \
        pytest tests/integration -q
"""

from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401  注册 ORM 模型
from app.ai.rag import retriever as rag
from app.db.base import Base
from app.models.chunk import DocumentChunk
from app.models.material import MeetingMaterial
from app.models.meeting import Meeting
from app.models.user import User

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="未设置 TEST_DATABASE_URL（PostgreSQL + pgvector 集成测试）",
)


@pytest.fixture()
def pg_session():
    engine = create_engine(TEST_DATABASE_URL, future=True)
    with engine.connect() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        connection.commit()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def _seed(session: Session) -> str:
    session.add(User(user_id="usr_a", name="alice", password_hash="x"))
    session.add(
        Meeting(
            meeting_id="mtg_a",
            user_id="usr_a",
            title="周会",
            topic=None,
            meeting_time=None,
        )
    )
    session.add(
        MeetingMaterial(
            material_id="mat_a",
            meeting_id="mtg_a",
            user_id="usr_a",
            file_name="a.txt",
            type="txt",
            source=None,
            storage_key="materials/mat_a.txt",
            content="占位",
            processing_status="processed",
        )
    )
    session.add_all(
        [
            DocumentChunk(
                chunk_id="chk_1",
                material_id="mat_a",
                content="完全一致",
                chunk_index=0,
                embedding=[1.0, 0.0, 0.0],
            ),
            DocumentChunk(
                chunk_id="chk_2",
                material_id="mat_a",
                content="部分一致",
                chunk_index=1,
                embedding=[0.7, 0.7, 0.0],
            ),
            DocumentChunk(
                chunk_id="chk_3",
                material_id="mat_a",
                content="完全无关",
                chunk_index=2,
                embedding=[0.0, 1.0, 0.0],
            ),
        ]
    )
    session.commit()
    return "usr_a"


def test_hnsw_indexes_exist(pg_session: Session) -> None:
    rows = pg_session.execute(
        text(
            "SELECT indexname FROM pg_indexes "
            "WHERE indexname IN ("
            "'ix_document_chunks_embedding_hnsw', "
            "'ix_knowledge_chunks_embedding_hnsw')"
        )
    ).all()
    assert {row[0] for row in rows} == {
        "ix_document_chunks_embedding_hnsw",
        "ix_knowledge_chunks_embedding_hnsw",
    }


def test_pgvector_retrieval_order_matches_cosine(
    pg_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    user_id = _seed(pg_session)
    monkeypatch.setattr(rag, "embed_query", lambda text, config: [1.0, 0.0, 0.0])

    retriever = rag.VectorRetriever(pg_session, user_id)
    assert retriever._backend() == "pgvector"

    results = retriever.retrieve("问题", user_id=user_id, top_k=3, min_score=0.0)

    assert [item.excerpt for item in results] == ["完全一致", "部分一致", "完全无关"]
    assert results[0].score == pytest.approx(1.0, abs=1e-6)
    assert results[1].score == pytest.approx(0.7, abs=1e-6)
    assert results[2].score == pytest.approx(0.0, abs=1e-6)


def test_pgvector_retrieval_filters_min_score(
    pg_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    user_id = _seed(pg_session)
    monkeypatch.setattr(rag, "embed_query", lambda text, config: [1.0, 0.0, 0.0])

    retriever = rag.VectorRetriever(pg_session, user_id)
    results = retriever.retrieve("问题", user_id=user_id, top_k=5, min_score=0.5)

    assert [item.excerpt for item in results] == ["完全一致", "部分一致"]


def test_pgvector_retrieval_scopes_by_user(
    pg_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    user_id = _seed(pg_session)
    monkeypatch.setattr(rag, "embed_query", lambda text, config: [1.0, 0.0, 0.0])

    retriever = rag.VectorRetriever(pg_session, user_id)
    results = retriever.retrieve("问题", user_id="usr_other", top_k=5, min_score=0.0)

    assert results == []


def test_hnsw_index_is_used_by_planner(
    pg_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """关闭顺序扫描后，ANN 查询必须走 HNSW 索引。"""
    _seed(pg_session)
    monkeypatch.setattr(rag, "embed_query", lambda text, config: [1.0, 0.0, 0.0])

    pg_session.execute(text("SET enable_seqscan = off"))
    plan = pg_session.execute(
        text(
            "EXPLAIN SELECT chunk_id FROM document_chunks "
            "ORDER BY embedding <=> :vector LIMIT 3"
        ),
        {"vector": "[1.0,0.0,0.0]"},
    ).all()
    joined = "\n".join(row[0] for row in plan)
    assert "ix_document_chunks_embedding_hnsw" in joined
