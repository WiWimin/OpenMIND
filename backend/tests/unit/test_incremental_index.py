"""增量索引：同用户、同库内复用分块；跨用户/跨库/指纹不匹配必须重建。

复用矩阵（docs/database.md）：
- 会议材料 `document_chunks`：同用户可跨会议复用；
- 个人知识库 `knowledge_chunks`：同用户可跨文档复用；
- 两库之间不互相复用，避免跨库脏召回。
"""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.repositories import (
    chunk_repository,
    knowledge_chunk_repository,
    knowledge_repository,
    material_repository,
    meeting_repository,
    user_repository,
)
from app.services import indexing_service, knowledge_service, material_service


class _EmbedCounter:
    """统计向量化调用次数（命中增量索引必须为 0）。"""

    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, texts: list[str], client: object) -> list[list[float]]:
        self.calls += 1
        return [[float(index), 1.0] for index, _ in enumerate(texts)]


class _FakeEmbeddingClient:
    def __init__(self, counter: _EmbedCounter) -> None:
        self._counter = counter

    def embed(self, texts: list[str]) -> list[list[float]]:
        return self._counter(texts, self)


@pytest.fixture()
def embed_counter(monkeypatch: pytest.MonkeyPatch) -> _EmbedCounter:
    counter = _EmbedCounter()
    monkeypatch.setattr(indexing_service, "embed_texts", counter)
    monkeypatch.setattr(
        knowledge_service,
        "build_embedding_client",
        lambda config: _FakeEmbeddingClient(counter),
    )
    return counter


def _seed_meeting(db: Session, *, user_id: str, meeting_id: str) -> None:
    meeting_repository.create(
        db,
        meeting_id=meeting_id,
        user_id=user_id,
        title="周会",
        topic=None,
        meeting_time=None,
    )


def _make_material(
    db: Session, *, user_id: str, meeting_id: str, material_id: str
):
    return material_repository.create(
        db,
        material_id=material_id,
        meeting_id=meeting_id,
        user_id=user_id,
        file_name="a.txt",
        material_type="txt",
        source=None,
        storage_key=f"materials/{material_id}.txt",
    )


def _make_document(db: Session, *, user_id: str, document_id: str):
    return knowledge_repository.create(
        db,
        document_id=document_id,
        user_id=user_id,
        file_name="doc.txt",
        document_type="txt",
        storage_key=f"knowledge/{document_id}.txt",
    )


# ---------- 会议材料库 ----------


def test_material_reuses_chunks_across_meetings(
    db_session: Session, embed_counter: _EmbedCounter
) -> None:
    user = user_repository.create(
        db_session, user_id="usr_a", name="alice", password_hash="x"
    )
    _seed_meeting(db_session, user_id=user.user_id, meeting_id="mtg_1")
    _seed_meeting(db_session, user_id=user.user_id, meeting_id="mtg_2")
    first = _make_material(
        db_session, user_id=user.user_id, meeting_id="mtg_1", material_id="mat_1"
    )
    second = _make_material(
        db_session, user_id=user.user_id, meeting_id="mtg_2", material_id="mat_2"
    )

    material_service._process_material(db_session, first, b"same bytes", "a.txt")
    assert embed_counter.calls == 1
    first_chunks = chunk_repository.count_by_material(db_session, "mat_1")
    assert first_chunks > 0

    material_service._process_material(db_session, second, b"same bytes", "a.txt")

    assert embed_counter.calls == 1  # 第二次未调用向量化
    assert second.processing_status == "processed"
    assert second.content_hash == first.content_hash
    assert second.index_fingerprint == first.index_fingerprint
    assert second.indexed_at is not None
    assert chunk_repository.count_by_material(db_session, "mat_2") == first_chunks


def test_material_different_content_still_embeds(
    db_session: Session, embed_counter: _EmbedCounter
) -> None:
    user = user_repository.create(
        db_session, user_id="usr_a", name="alice", password_hash="x"
    )
    _seed_meeting(db_session, user_id=user.user_id, meeting_id="mtg_1")
    first = _make_material(
        db_session, user_id=user.user_id, meeting_id="mtg_1", material_id="mat_1"
    )
    second = _make_material(
        db_session, user_id=user.user_id, meeting_id="mtg_1", material_id="mat_2"
    )

    material_service._process_material(db_session, first, b"alpha", "a.txt")
    material_service._process_material(db_session, second, b"beta", "a.txt")

    assert embed_counter.calls == 2


def test_material_never_reuses_other_users_chunks(
    db_session: Session, embed_counter: _EmbedCounter
) -> None:
    alice = user_repository.create(
        db_session, user_id="usr_a", name="alice", password_hash="x"
    )
    bob = user_repository.create(
        db_session, user_id="usr_b", name="bob", password_hash="x"
    )
    _seed_meeting(db_session, user_id=alice.user_id, meeting_id="mtg_a")
    _seed_meeting(db_session, user_id=bob.user_id, meeting_id="mtg_b")
    alice_material = _make_material(
        db_session, user_id=alice.user_id, meeting_id="mtg_a", material_id="mat_a"
    )
    bob_material = _make_material(
        db_session, user_id=bob.user_id, meeting_id="mtg_b", material_id="mat_b"
    )

    material_service._process_material(db_session, alice_material, b"same bytes", "a.txt")
    material_service._process_material(db_session, bob_material, b"same bytes", "a.txt")

    assert embed_counter.calls == 2  # 不得复用他人分块
    assert chunk_repository.count_by_material(db_session, "mat_b") > 0


def test_material_rebuilds_on_fingerprint_change(
    db_session: Session, embed_counter: _EmbedCounter, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = user_repository.create(
        db_session, user_id="usr_a", name="alice", password_hash="x"
    )
    _seed_meeting(db_session, user_id=user.user_id, meeting_id="mtg_1")
    first = _make_material(
        db_session, user_id=user.user_id, meeting_id="mtg_1", material_id="mat_1"
    )
    second = _make_material(
        db_session, user_id=user.user_id, meeting_id="mtg_1", material_id="mat_2"
    )

    material_service._process_material(db_session, first, b"same bytes", "a.txt")
    # 模拟换 Embedding 模型/分块参数：指纹变化，旧分块不可复用
    monkeypatch.setattr(
        material_service,
        "build_index_fingerprint",
        lambda settings: "another-fingerprint",
    )
    material_service._process_material(db_session, second, b"same bytes", "a.txt")

    assert embed_counter.calls == 2
    assert second.index_fingerprint == "another-fingerprint"


def test_material_incremental_disabled_reembeds(
    db_session: Session,
    embed_counter: _EmbedCounter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import get_settings

    user = user_repository.create(
        db_session, user_id="usr_a", name="alice", password_hash="x"
    )
    _seed_meeting(db_session, user_id=user.user_id, meeting_id="mtg_1")
    first = _make_material(
        db_session, user_id=user.user_id, meeting_id="mtg_1", material_id="mat_1"
    )
    second = _make_material(
        db_session, user_id=user.user_id, meeting_id="mtg_1", material_id="mat_2"
    )

    material_service._process_material(db_session, first, b"same bytes", "a.txt")
    base = get_settings()
    monkeypatch.setattr(
        material_service,
        "get_settings",
        lambda: base.model_copy(update={"rag_incremental_index_enabled": False}),
    )
    material_service._process_material(db_session, second, b"same bytes", "a.txt")

    assert embed_counter.calls == 2


def test_material_reused_chunks_are_independently_deletable(
    db_session: Session, embed_counter: _EmbedCounter
) -> None:
    """源材料删除后，已复用的分块仍保留（复制而非引用）。"""
    user = user_repository.create(
        db_session, user_id="usr_a", name="alice", password_hash="x"
    )
    _seed_meeting(db_session, user_id=user.user_id, meeting_id="mtg_1")
    _seed_meeting(db_session, user_id=user.user_id, meeting_id="mtg_2")
    first = _make_material(
        db_session, user_id=user.user_id, meeting_id="mtg_1", material_id="mat_1"
    )
    second = _make_material(
        db_session, user_id=user.user_id, meeting_id="mtg_2", material_id="mat_2"
    )

    material_service._process_material(db_session, first, b"same bytes", "a.txt")
    material_service._process_material(db_session, second, b"same bytes", "a.txt")

    chunk_repository.delete_by_material(db_session, "mat_1")
    db_session.commit()

    assert chunk_repository.count_by_material(db_session, "mat_2") > 0


# ---------- 个人知识库 ----------


def test_document_reuses_chunks_across_documents(
    db_session: Session, embed_counter: _EmbedCounter
) -> None:
    user = user_repository.create(
        db_session, user_id="usr_a", name="alice", password_hash="x"
    )
    first = _make_document(db_session, user_id=user.user_id, document_id="kdoc_1")
    second = _make_document(db_session, user_id=user.user_id, document_id="kdoc_2")

    knowledge_service._process_document(db_session, first, b"same bytes", "doc.txt")
    knowledge_service._process_document(db_session, second, b"same bytes", "doc.txt")

    assert embed_counter.calls == 1
    assert second.processing_status == "processed"
    assert (
        knowledge_chunk_repository.count_by_document(db_session, "kdoc_2")
        == knowledge_chunk_repository.count_by_document(db_session, "kdoc_1")
        > 0
    )


def test_document_never_reuses_other_users_chunks(
    db_session: Session, embed_counter: _EmbedCounter
) -> None:
    alice = user_repository.create(
        db_session, user_id="usr_a", name="alice", password_hash="x"
    )
    bob = user_repository.create(
        db_session, user_id="usr_b", name="bob", password_hash="x"
    )
    first = _make_document(db_session, user_id=alice.user_id, document_id="kdoc_a")
    second = _make_document(db_session, user_id=bob.user_id, document_id="kdoc_b")

    knowledge_service._process_document(db_session, first, b"same bytes", "doc.txt")
    knowledge_service._process_document(db_session, second, b"same bytes", "doc.txt")

    assert embed_counter.calls == 2


# ---------- 跨库隔离：会议材料 ↔ 个人知识库 ----------


def test_material_does_not_reuse_knowledge_chunks(
    db_session: Session, embed_counter: _EmbedCounter
) -> None:
    user = user_repository.create(
        db_session, user_id="usr_a", name="alice", password_hash="x"
    )
    _seed_meeting(db_session, user_id=user.user_id, meeting_id="mtg_1")
    document = _make_document(db_session, user_id=user.user_id, document_id="kdoc_1")
    material = _make_material(
        db_session, user_id=user.user_id, meeting_id="mtg_1", material_id="mat_1"
    )

    knowledge_service._process_document(db_session, document, b"same bytes", "doc.txt")
    material_service._process_material(db_session, material, b"same bytes", "a.txt")

    assert embed_counter.calls == 2  # 跨库不复用
    assert knowledge_chunk_repository.count_by_document(db_session, "kdoc_1") > 0
    assert chunk_repository.count_by_material(db_session, "mat_1") > 0


def test_document_does_not_reuse_material_chunks(
    db_session: Session, embed_counter: _EmbedCounter
) -> None:
    user = user_repository.create(
        db_session, user_id="usr_a", name="alice", password_hash="x"
    )
    _seed_meeting(db_session, user_id=user.user_id, meeting_id="mtg_1")
    material = _make_material(
        db_session, user_id=user.user_id, meeting_id="mtg_1", material_id="mat_1"
    )
    document = _make_document(db_session, user_id=user.user_id, document_id="kdoc_1")

    material_service._process_material(db_session, material, b"same bytes", "a.txt")
    knowledge_service._process_document(db_session, document, b"same bytes", "doc.txt")

    assert embed_counter.calls == 2  # 跨库不复用
    assert knowledge_chunk_repository.count_by_document(db_session, "kdoc_1") > 0
