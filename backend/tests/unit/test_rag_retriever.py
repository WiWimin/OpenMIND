import pytest
from sqlalchemy.orm import Session

from app.ai.rag import retriever as rag
from app.core.exceptions import AppError
from app.models.chunk import DocumentChunk
from app.models.knowledge_chunk import KnowledgeChunk
from app.repositories import (
    knowledge_repository,
    material_repository,
    meeting_repository,
    user_repository,
)


def _seed_user_meeting_material(
    db: Session,
    *,
    name: str,
    meeting_id: str,
    material_id: str,
    chunk_id: str,
    content: str,
    embedding: list[float],
) -> str:
    user = user_repository.create(
        db, user_id=f"usr_{name}", name=name, password_hash="x"
    )
    meeting_repository.create(
        db,
        meeting_id=meeting_id,
        user_id=user.user_id,
        title="周会",
        topic=None,
        meeting_time=None,
    )
    material_repository.create(
        db,
        material_id=material_id,
        meeting_id=meeting_id,
        user_id=user.user_id,
        file_name="a.txt",
        material_type="txt",
        source=None,
        storage_key=f"materials/{material_id}.txt",
    )
    db.add(
        DocumentChunk(
            chunk_id=chunk_id,
            material_id=material_id,
            content=content,
            chunk_index=0,
            embedding=embedding,
        )
    )
    db.commit()
    return user.user_id


def test_vector_retriever_scopes_by_user_and_score(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(rag, "embed_query", lambda text, config: [1.0, 0.0])
    alice_id = _seed_user_meeting_material(
        db_session,
        name="alice",
        meeting_id="mtg_a",
        material_id="mat_a",
        chunk_id="chk_a",
        content="相关片段",
        embedding=[1.0, 0.0],
    )
    _seed_user_meeting_material(
        db_session,
        name="bob",
        meeting_id="mtg_b",
        material_id="mat_b",
        chunk_id="chk_b",
        content="他人片段",
        embedding=[1.0, 0.0],
    )
    db_session.add(
        DocumentChunk(
            chunk_id="chk_a2",
            material_id="mat_a",
            content="无关片段",
            chunk_index=1,
            embedding=[0.0, 1.0],
        )
    )
    db_session.commit()

    retriever = rag.VectorRetriever(db_session, alice_id)
    results = retriever.retrieve("问题", user_id=alice_id, min_score=0.3)

    assert [item.material_id for item in results] == ["mat_a"]
    assert results[0].excerpt == "相关片段"


def test_vector_retriever_current_meeting_scope(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(rag, "embed_query", lambda text, config: [1.0, 0.0])
    alice_id = _seed_user_meeting_material(
        db_session,
        name="alice",
        meeting_id="mtg_a",
        material_id="mat_a",
        chunk_id="chk_a",
        content="会议A片段",
        embedding=[1.0, 0.0],
    )
    meeting_repository.create(
        db_session,
        meeting_id="mtg_a2",
        user_id=alice_id,
        title="第二次会议",
        topic=None,
        meeting_time=None,
    )
    material_repository.create(
        db_session,
        material_id="mat_a2",
        meeting_id="mtg_a2",
        user_id=alice_id,
        file_name="b.txt",
        material_type="txt",
        source=None,
        storage_key="materials/mat_a2.txt",
    )
    db_session.add(
        DocumentChunk(
            chunk_id="chk_a2x",
            material_id="mat_a2",
            content="会议A2片段",
            chunk_index=0,
            embedding=[1.0, 0.0],
        )
    )
    db_session.commit()

    retriever = rag.VectorRetriever(db_session, alice_id)
    results = retriever.retrieve(
        "问题",
        user_id=alice_id,
        scope="current_meeting",
        current_meeting_id="mtg_a",
    )
    assert [item.meeting_id for item in results] == ["mtg_a"]


def test_vector_retriever_no_chunks(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(rag, "embed_query", lambda text, config: [1.0, 0.0])
    retriever = rag.VectorRetriever(db_session, "usr_none")
    assert retriever.retrieve("问题", user_id="usr_none") == []


def test_vector_retriever_knowledge_base_scope(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(rag, "embed_query", lambda text, config: [1.0, 0.0])
    alice = user_repository.create(
        db_session, user_id="usr_alice", name="alice", password_hash="x"
    )
    bob = user_repository.create(
        db_session, user_id="usr_bob", name="bob", password_hash="x"
    )
    alice_doc = knowledge_repository.create(
        db_session,
        document_id="kdoc_a",
        user_id=alice.user_id,
        file_name="alpha.txt",
        document_type="txt",
        storage_key="knowledge/kdoc_a.txt",
    )
    bob_doc = knowledge_repository.create(
        db_session,
        document_id="kdoc_b",
        user_id=bob.user_id,
        file_name="bob.txt",
        document_type="txt",
        storage_key="knowledge/kdoc_b.txt",
    )
    db_session.add_all(
        [
            KnowledgeChunk(
                chunk_id="kchk_a",
                document_id=alice_doc.document_id,
                content="知识库相关内容",
                chunk_index=0,
                embedding=[1.0, 0.0],
            ),
            KnowledgeChunk(
                chunk_id="kchk_b",
                document_id=bob_doc.document_id,
                content="他人知识库内容",
                chunk_index=0,
                embedding=[1.0, 0.0],
            ),
        ]
    )
    db_session.commit()

    retriever = rag.VectorRetriever(db_session, alice.user_id)
    results = retriever.retrieve(
        "问题", user_id=alice.user_id, scope="knowledge_base"
    )

    assert [item.document_id for item in results] == ["kdoc_a"]
    assert results[0].document_name == "alpha.txt"
    assert results[0].meeting_id is None
    assert results[0].material_id is None
    assert results[0].excerpt == "知识库相关内容"


# ---------- 检索后端分流与配置化默认值 ----------


def test_vector_retriever_backend_auto_is_python_on_sqlite(
    db_session: Session,
) -> None:
    retriever = rag.VectorRetriever(db_session, "usr_none")
    assert retriever._backend() == "python"


def test_vector_retriever_explicit_pgvector_on_sqlite_raises(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.config import get_settings

    base = get_settings()
    monkeypatch.setattr(
        rag,
        "get_settings",
        lambda: base.model_copy(update={"rag_vector_backend": "pgvector"}),
    )
    retriever = rag.VectorRetriever(db_session, "usr_none")
    with pytest.raises(AppError) as excinfo:
        retriever._backend()
    assert excinfo.value.error_code == "INTERNAL_ERROR"


def test_vector_retriever_reads_defaults_from_settings(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """top_k/min_score 缺省时由 RAG_TOP_K / RAG_MIN_SCORE 决定。"""
    from app.core.config import get_settings

    base = get_settings()
    monkeypatch.setattr(
        rag,
        "get_settings",
        lambda: base.model_copy(update={"rag_top_k": 1, "rag_min_score": 0.3}),
    )
    monkeypatch.setattr(rag, "embed_query", lambda text, config: [1.0, 0.0])
    alice_id = _seed_user_meeting_material(
        db_session,
        name="alice",
        meeting_id="mtg_a",
        material_id="mat_a",
        chunk_id="chk_a",
        content="高分片段",
        embedding=[1.0, 0.0],
    )
    db_session.add(
        DocumentChunk(
            chunk_id="chk_a2",
            material_id="mat_a",
            content="次高分片段",
            chunk_index=1,
            embedding=[1.0, 0.0],
        )
    )
    db_session.commit()

    retriever = rag.VectorRetriever(db_session, alice_id)
    results = retriever.retrieve("问题", user_id=alice_id)

    assert len(results) == 1  # RAG_TOP_K=1 截断


def test_vector_retriever_pgvector_scores_and_filters(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """PG 路径：距离换算 1-dist、min_score 过滤、top_k 截断、过采样上限下发 SQL。"""
    monkeypatch.setattr(rag, "embed_query", lambda text, config: [1.0, 0.0])
    monkeypatch.setattr(rag.VectorRetriever, "_backend", lambda self: "pgvector")
    monkeypatch.setattr(rag.VectorRetriever, "_set_hnsw_ef_search", lambda self: None)
    alice_id = _seed_user_meeting_material(
        db_session,
        name="alice",
        meeting_id="mtg_a",
        material_id="mat_a",
        chunk_id="chk_seed",
        content="占位片段",
        embedding=[1.0, 0.0],
    )

    near = DocumentChunk(
        chunk_id="chk_near",
        material_id="mat_a",
        content="近邻片段",
        chunk_index=0,
        embedding=[1.0, 0.0],
    )
    far = DocumentChunk(
        chunk_id="chk_far",
        material_id="mat_a",
        content="远端片段",
        chunk_index=1,
        embedding=[0.0, 1.0],
    )

    class _FakeResult:
        def __init__(self, rows):
            self._rows = rows

        def all(self):
            return self._rows

    captured: dict[str, object] = {}

    def fake_execute(statement, *args, **kwargs):
        captured["statement"] = statement
        return _FakeResult([(near, "mtg_a", 0.2), (far, "mtg_a", 0.9)])

    retriever = rag.VectorRetriever(db_session, alice_id)
    monkeypatch.setattr(db_session, "execute", fake_execute)
    results = retriever.retrieve("问题", user_id=alice_id, top_k=5, min_score=0.3)

    assert [item.excerpt for item in results] == ["近邻片段"]
    assert results[0].score == pytest.approx(0.8)  # 1 - 0.2
    assert results[0].meeting_id == "mtg_a"
    assert results[0].material_id == "mat_a"

    # 过采样上限必须下发到 SQL：top_k(5) * rag_ann_oversample(4) = 20
    from sqlalchemy.dialects import postgresql

    compiled = str(
        captured["statement"].compile(
            dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
        )
    )
    assert "LIMIT 20" in compiled


def test_vector_retriever_pgvector_truncates_to_top_k(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(rag, "embed_query", lambda text, config: [1.0, 0.0])
    monkeypatch.setattr(rag.VectorRetriever, "_backend", lambda self: "pgvector")
    monkeypatch.setattr(rag.VectorRetriever, "_set_hnsw_ef_search", lambda self: None)
    alice_id = _seed_user_meeting_material(
        db_session,
        name="alice",
        meeting_id="mtg_a",
        material_id="mat_a",
        chunk_id="chk_seed",
        content="占位片段",
        embedding=[1.0, 0.0],
    )

    rows = [
        (
            DocumentChunk(
                chunk_id=f"chk_{index}",
                material_id="mat_a",
                content=f"片段{index}",
                chunk_index=index,
                embedding=[1.0, 0.0],
            ),
            "mtg_a",
            0.1 * index,
        )
        for index in range(5)
    ]

    class _FakeResult:
        def __init__(self, rows):
            self._rows = rows

        def all(self):
            return self._rows

    retriever = rag.VectorRetriever(db_session, alice_id)
    monkeypatch.setattr(
        db_session, "execute", lambda statement, *args, **kwargs: _FakeResult(rows)
    )
    results = retriever.retrieve("问题", user_id=alice_id, top_k=2, min_score=0.0)
    assert len(results) == 2
    assert [item.score for item in results] == pytest.approx([1.0, 0.9])
