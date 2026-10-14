import pytest
from sqlalchemy.orm import Session

from app.ai.rag import retriever as rag
from app.models.chunk import DocumentChunk
from app.repositories import material_repository, meeting_repository, user_repository


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
    monkeypatch.setattr(rag, "embed_query", lambda text: [1.0, 0.0])
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
    monkeypatch.setattr(rag, "embed_query", lambda text: [1.0, 0.0])
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
    monkeypatch.setattr(rag, "embed_query", lambda text: [1.0, 0.0])
    retriever = rag.VectorRetriever(db_session, "usr_none")
    assert retriever.retrieve("问题", user_id="usr_none") == []
