import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.chunk import DocumentChunk
from app.repositories import material_repository, meeting_repository, user_repository
from app.services import indexing_service


def _seed_material(db: Session, *, content: str) -> object:
    user = user_repository.create(db, user_id="usr_1", name="alice", password_hash="x")
    meeting = meeting_repository.create(
        db, meeting_id="mtg_1", user_id=user.user_id, title="周会", topic=None, meeting_time=None
    )
    material = material_repository.create(
        db,
        material_id="mat_1",
        meeting_id=meeting.meeting_id,
        user_id=user.user_id,
        file_name="a.txt",
        material_type="txt",
        source=None,
        storage_key="materials/mat_1.txt",
    )
    material.content = content
    db.commit()
    return material


def _fake_vectors(texts: list[str], client: object) -> list[list[float]]:
    return [[float(index), 1.0] for index, _ in enumerate(texts)]


def test_index_material_creates_chunks(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(indexing_service, "embed_texts", _fake_vectors)
    material = _seed_material(db_session, content="句子。" * 500)

    rows = indexing_service.index_material(db_session, material)
    assert len(rows) >= 2
    assert [row.chunk_index for row in rows] == list(range(len(rows)))
    assert all(row.embedding is not None for row in rows)
    assert all(row.material_id == "mat_1" for row in rows)


def test_index_material_replaces_existing(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(indexing_service, "embed_texts", _fake_vectors)
    material = _seed_material(db_session, content="句子。" * 500)

    first = indexing_service.index_material(db_session, material)
    second = indexing_service.index_material(db_session, material)

    assert len(first) == len(second)
    total = db_session.execute(
        select(func.count()).select_from(DocumentChunk)
    ).scalar_one()
    assert total == len(second)


def test_index_material_empty_content(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(indexing_service, "embed_texts", lambda texts, client: [])
    material = _seed_material(db_session, content="")

    rows = indexing_service.index_material(db_session, material)
    assert rows == []
