import pytest
from sqlalchemy.orm import Session

from app.repositories import material_repository, meeting_repository, user_repository
from app.services import material_service


def _seed_material(db: Session):
    user = user_repository.create(db, user_id="usr_1", name="alice", password_hash="x")
    meeting = meeting_repository.create(
        db,
        meeting_id="mtg_1",
        user_id=user.user_id,
        title="周会",
        topic=None,
        meeting_time=None,
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
    material.parse_error = "old error"
    db.commit()
    return material


def test_process_material_success_clears_parse_error(db_session: Session) -> None:
    material = _seed_material(db_session)

    material_service._process_material(db_session, material, b"hello", "a.txt")
    db_session.refresh(material)

    assert material.processing_status == "processed"
    assert material.parse_error is None


def test_process_material_unexpected_error_marks_failed(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    material = _seed_material(db_session)

    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(material_service.indexing_service, "index_material", boom)

    with pytest.raises(RuntimeError):
        material_service._process_material(db_session, material, b"hello", "a.txt")

    db_session.refresh(material)
    assert material.processing_status == "failed"
    assert material.parse_error
