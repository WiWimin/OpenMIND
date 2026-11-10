"""任务执行器：状态流转、进度、AppError 与未知异常归一。"""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.repositories import job_repository
from app.services import job_service, task_runner


def _job_id(db: Session) -> str:
    job = job_service.create_job(
        db,
        user_id="usr_runner",
        job_type="material_parse",
        resource_type="material",
        resource_id="mat_x",
    )
    return job.job_id


def _reload(db: Session, job_id: str):
    # run_job 结束时会 close 会话（实例转 detached），必须重新查询
    job = job_repository.get(db, job_id)
    assert job is not None
    return job


def test_run_job_success_marks_succeeded(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    job_id = _job_id(db_session)
    monkeypatch.setattr(task_runner, "session_factory", lambda: db_session)

    def fn(db: Session, progress) -> None:
        progress(50)

    task_runner.run_job(job_id, fn)

    job = _reload(db_session, job_id)
    assert job.status == "succeeded"
    assert job.progress == 100
    assert job.started_at is not None
    assert job.finished_at is not None
    assert job.error_code is None


def test_run_job_app_error_records_error_code(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    job_id = _job_id(db_session)
    monkeypatch.setattr(task_runner, "session_factory", lambda: db_session)

    def fn(db: Session, progress) -> None:
        raise AppError("MODEL_TIMEOUT", "模型调用超时", retryable=True)

    task_runner.run_job(job_id, fn)

    job = _reload(db_session, job_id)
    assert job.status == "failed"
    assert job.error_code == "MODEL_TIMEOUT"
    assert job.error_message == "模型调用超时"


def test_run_job_unknown_exception_becomes_internal_error(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    job_id = _job_id(db_session)
    monkeypatch.setattr(task_runner, "session_factory", lambda: db_session)

    def fn(db: Session, progress) -> None:
        raise RuntimeError("boom")

    task_runner.run_job(job_id, fn)

    job = _reload(db_session, job_id)
    assert job.status == "failed"
    assert job.error_code == "INTERNAL_ERROR"
    assert job.error_message == "任务执行失败"


def test_run_job_skips_non_pending(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    job_id = _job_id(db_session)
    job = _reload(db_session, job_id)
    job_service.mark_succeeded(db_session, job)
    monkeypatch.setattr(task_runner, "session_factory", lambda: db_session)
    called = {"ran": False}

    def fn(db: Session, progress) -> None:
        called["ran"] = True

    task_runner.run_job(job_id, fn)

    assert called["ran"] is False
    assert _reload(db_session, job_id).status == "succeeded"
