"""B3 异步任务：202 受理、任务查询、状态流转、超时回收与归属隔离。

默认环境 `ASYNC_JOBS_ENABLED=false`（conftest），本模块用 `async_enabled`
上下文临时开启；TestClient 会在响应返回后执行 BackgroundTasks，
因此查询任务时任务通常已进入终态。
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.ai.preparation import PreparationDraft
from app.core.config import get_settings
from app.models.async_job import AsyncJob
from app.models.user import utc_now
from app.services import (
    audio_service,
    job_tasks,
    knowledge_service,
    material_service,
    minutes_service,
    preparation_service,
)

REGISTER = "/api/v1/auth/register"
MEETINGS = "/api/v1/meetings"
JOBS = "/api/v1/jobs"
PASSWORD = "secret123"


@contextmanager
def async_enabled() -> Iterator[None]:
    os.environ["ASYNC_JOBS_ENABLED"] = "true"
    get_settings.cache_clear()
    try:
        yield
    finally:
        os.environ["ASYNC_JOBS_ENABLED"] = "false"
        get_settings.cache_clear()


@pytest.fixture()
def media_root(tmp_path, monkeypatch: pytest.MonkeyPatch):
    """存储目录重定向到 tmp；任务体（job_tasks）与服务层共用同一配置。"""
    base = get_settings()

    def fake_settings():
        return base.model_copy(update={"storage_dir": str(tmp_path)})

    for module in (
        material_service,
        knowledge_service,
        audio_service,
        job_tasks,
    ):
        monkeypatch.setattr(module, "get_settings", fake_settings)
    return tmp_path


def _auth(client: TestClient, name: str = "alice") -> dict[str, str]:
    response = client.post(REGISTER, json={"name": name, "password": PASSWORD})
    token = response.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _user_id(client: TestClient, headers: dict[str, str]) -> str:
    return client.get("/api/v1/auth/me", headers=headers).json()["data"]["user_id"]


def _meeting(client: TestClient, headers: dict[str, str]) -> dict:
    response = client.post(MEETINGS, json={"title": "异步会议"}, headers=headers)
    assert response.status_code == 201
    return response.json()["data"]


def _job(client: TestClient, headers: dict[str, str], job_id: str) -> dict:
    response = client.get(f"{JOBS}/{job_id}", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["data"]


@pytest.fixture()
def fake_embeddings(monkeypatch: pytest.MonkeyPatch) -> None:
    """知识库索引向量化打桩：避免后台任务发起真实 Embedding 调用。"""
    vector = [1.0] + [0.0] * 1023

    class _FakeClient:
        def embed(self, texts: list[str]) -> list[list[float]]:
            return [list(vector) for _ in texts]

    from app.ai.rag import retriever as rag_retriever

    monkeypatch.setattr(
        knowledge_service,
        "build_embedding_client",
        lambda config: _FakeClient(),
    )
    monkeypatch.setattr(
        rag_retriever, "embed_query", lambda *a, **k: list(vector)
    )


# ============================ 上传 / 重试 202 ============================


def test_material_upload_returns_202_and_job_succeeds(
    client: TestClient, media_root
) -> None:
    headers = _auth(client)
    meeting = _meeting(client, headers)

    with async_enabled():
        response = client.post(
            f"{MEETINGS}/{meeting['meeting_id']}/materials",
            files={"file": ("plan.txt", b"hello", "text/plain")},
            headers=headers,
        )

    assert response.status_code == 202, response.text
    job = response.json()["data"]["job"]
    assert job["job_type"] == "material_parse"
    assert job["resource_type"] == "material"
    assert job["resource_id"]

    data = _job(client, headers, job["job_id"])
    assert data["status"] == "succeeded"
    assert data["progress"] == 100
    assert data["error_code"] is None
    assert data["started_at"] and data["finished_at"]

    material = client.get(
        f"/api/v1/materials/{job['resource_id']}", headers=headers
    ).json()["data"]
    assert material["processing_status"] == "processed"


def test_material_parse_failure_marks_job_failed(
    client: TestClient, media_root
) -> None:
    headers = _auth(client)
    meeting = _meeting(client, headers)

    with async_enabled():
        response = client.post(
            f"{MEETINGS}/{meeting['meeting_id']}/materials",
            files={"file": ("broken.pdf", b"not a real pdf", "application/pdf")},
            headers=headers,
        )

    assert response.status_code == 202, response.text
    job = response.json()["data"]["job"]

    data = _job(client, headers, job["job_id"])
    assert data["status"] == "failed"
    assert data["error_code"] == "FILE_PARSE_FAILED"
    assert data["error_message"]

    # 统一失败策略照常生效：资源落 failed 并保留文件
    material = client.get(
        f"/api/v1/materials/{job['resource_id']}", headers=headers
    ).json()["data"]
    assert material["processing_status"] == "failed"
    assert material["parse_error_code"] == "FILE_PARSE_FAILED"
    assert (media_root / "materials" / f"{job['resource_id']}.pdf").exists()


def test_material_retry_returns_202_and_recovers(
    client: TestClient, media_root, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers = _auth(client)
    meeting = _meeting(client, headers)
    with async_enabled():
        failed = client.post(
            f"{MEETINGS}/{meeting['meeting_id']}/materials",
            files={"file": ("broken.pdf", b"not a real pdf", "application/pdf")},
            headers=headers,
        ).json()["data"]["job"]
        assert _job(client, headers, failed["job_id"])["status"] == "failed"
        material_id = failed["resource_id"]

        class _Parsed:
            content = "恢复后的正文"

        monkeypatch.setattr(material_service, "parse_bytes", lambda *a, **k: _Parsed())
        retry = client.post(f"/api/v1/materials/{material_id}/retry", headers=headers)

    assert retry.status_code == 202, retry.text
    job = retry.json()["data"]["job"]
    assert job["job_type"] == "material_parse"
    data = _job(client, headers, job["job_id"])
    assert data["status"] == "succeeded"

    material = client.get(f"/api/v1/materials/{material_id}", headers=headers).json()[
        "data"
    ]
    assert material["processing_status"] == "processed"
    assert material["parse_error"] is None


def test_knowledge_upload_returns_202_and_job_succeeds(
    client: TestClient, media_root, fake_embeddings: None
) -> None:
    headers = _auth(client)

    with async_enabled():
        response = client.post(
            "/api/v1/knowledge/documents",
            files={"file": ("manual.txt", "知识库正文".encode(), "text/plain")},
            headers=headers,
        )

    assert response.status_code == 202, response.text
    job = response.json()["data"]["job"]
    assert job["job_type"] == "knowledge_parse"
    assert job["resource_type"] == "knowledge_document"

    data = _job(client, headers, job["job_id"])
    assert data["status"] == "succeeded"

    document = client.get(
        f"/api/v1/knowledge/documents/{job['resource_id']}", headers=headers
    ).json()["data"]
    assert document["processing_status"] == "processed"


def test_audio_upload_returns_202_and_job_succeeds(
    client: TestClient, media_root, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers = _auth(client)
    meeting = _meeting(client, headers)
    monkeypatch.setattr(audio_service, "transcribe_file", lambda *a, **k: "转写正文")

    with async_enabled():
        response = client.post(
            f"{MEETINGS}/{meeting['meeting_id']}/audio",
            files={"file": ("voice.mp3", b"\x00\x01", "audio/mpeg")},
            headers=headers,
        )

    assert response.status_code == 202, response.text
    job = response.json()["data"]["job"]
    assert job["job_type"] == "audio_transcribe"
    assert job["resource_type"] == "audio"

    data = _job(client, headers, job["job_id"])
    assert data["status"] == "succeeded"

    audio = client.get(f"/api/v1/audio/{job['resource_id']}", headers=headers).json()[
        "data"
    ]
    assert audio["status"] == "transcribed"


# ============================ 纪要 / 准备 202 ============================


def test_minutes_generate_returns_202_and_job_succeeds(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers = _auth(client)
    meeting = _meeting(client, headers)
    monkeypatch.setattr(
        minutes_service, "generate_text", lambda *a, **k: "生成的纪要正文"
    )

    with async_enabled():
        response = client.post(
            f"{MEETINGS}/{meeting['meeting_id']}/minutes/generate",
            json={"record_ids": [], "include_action_items": False},
            headers=headers,
        )

    assert response.status_code == 202, response.text
    job = response.json()["data"]["job"]
    assert job["job_type"] == "minutes_generate"
    # 纪要生成到任务结束才创建资源，受理时 resource_id 为空
    assert job["resource_id"] is None

    data = _job(client, headers, job["job_id"])
    assert data["status"] == "succeeded"

    minutes = client.get(
        f"{MEETINGS}/{meeting['meeting_id']}/minutes", headers=headers
    ).json()["data"]["items"]
    assert len(minutes) == 1
    assert minutes[0]["status"] == "draft"
    assert minutes[0]["content"] == "生成的纪要正文"


def test_prepare_returns_202_placeholder_becomes_draft(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers = _auth(client)
    meeting = _meeting(client, headers)
    monkeypatch.setattr(
        preparation_service,
        "generate_draft",
        lambda *a, **k: PreparationDraft(summary="摘要", checklist=["项一"]),
    )

    with async_enabled():
        response = client.post(
            f"{MEETINGS}/{meeting['meeting_id']}/prepare", json={}, headers=headers
        )

    assert response.status_code == 202, response.text
    job = response.json()["data"]["job"]
    assert job["job_type"] == "preparation_generate"
    assert job["resource_type"] == "preparation"
    preparation_id = job["resource_id"]
    assert preparation_id

    data = _job(client, headers, job["job_id"])
    assert data["status"] == "succeeded"

    preparation = client.get(
        f"/api/v1/preparations/{preparation_id}", headers=headers
    ).json()["data"]
    assert preparation["status"] == "draft"
    assert preparation["summary"] == "摘要"


def test_prepare_failure_marks_placeholder_and_job_failed(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.exceptions import AppError

    headers = _auth(client)
    meeting = _meeting(client, headers)

    def timeout(*args, **kwargs):
        raise AppError("MODEL_TIMEOUT", "模型调用超时", http_status=504, retryable=True)

    monkeypatch.setattr(preparation_service, "generate_draft", timeout)

    with async_enabled():
        response = client.post(
            f"{MEETINGS}/{meeting['meeting_id']}/prepare", json={}, headers=headers
        )

    assert response.status_code == 202, response.text
    job = response.json()["data"]["job"]

    data = _job(client, headers, job["job_id"])
    assert data["status"] == "failed"
    assert data["error_code"] == "MODEL_TIMEOUT"

    preparation = client.get(
        f"/api/v1/preparations/{job['resource_id']}", headers=headers
    ).json()["data"]
    assert preparation["status"] == "failed"


# ============================ 任务查询与回收 ============================


def test_job_list_filters_by_resource(client: TestClient, media_root) -> None:
    headers = _auth(client)
    meeting = _meeting(client, headers)
    with async_enabled():
        first = client.post(
            f"{MEETINGS}/{meeting['meeting_id']}/materials",
            files={"file": ("a.txt", b"one", "text/plain")},
            headers=headers,
        ).json()["data"]["job"]
        client.post(
            f"{MEETINGS}/{meeting['meeting_id']}/materials",
            files={"file": ("b.txt", b"two", "text/plain")},
            headers=headers,
        )

    response = client.get(
        f"{JOBS}?resource_type=material&resource_id={first['resource_id']}",
        headers=headers,
    )
    assert response.status_code == 200
    items = response.json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["job_id"] == first["job_id"]

    all_jobs = client.get(JOBS, headers=headers)
    assert all_jobs.status_code == 200
    assert len(all_jobs.json()["data"]["items"]) == 2


def test_unknown_job_returns_404(client: TestClient) -> None:
    headers = _auth(client)
    response = client.get(f"{JOBS}/job_missing", headers=headers)
    assert response.status_code == 404
    assert response.json()["error_code"] == "RESOURCE_NOT_FOUND"


def test_job_isolation_between_users(
    client: TestClient, db_session: Session
) -> None:
    alice = _auth(client, "alice")
    bob = _auth(client, "bob")
    job = AsyncJob(
        job_id="job_alice_only",
        user_id=_user_id(client, alice),
        job_type="material_parse",
        resource_type="material",
        resource_id="mat_x",
        status="pending",
        progress=0,
        created_at=utc_now(),
    )
    db_session.add(job)
    db_session.commit()

    # 他人任务视为不存在
    assert client.get(f"{JOBS}/job_alice_only", headers=bob).status_code == 404
    # 列表只返回本人任务
    listed = client.get(JOBS, headers=bob).json()["data"]["items"]
    assert listed == []
    own = client.get(JOBS, headers=alice).json()["data"]["items"]
    assert [item["job_id"] for item in own] == ["job_alice_only"]


def test_stale_running_job_lazy_reaped_as_timeout(
    client: TestClient, db_session: Session
) -> None:
    headers = _auth(client)
    stale_id = "job_stale_running"
    job = AsyncJob(
        job_id=stale_id,
        user_id=_user_id(client, headers),
        job_type="material_parse",
        resource_type="material",
        resource_id="mat_old",
        status="running",
        progress=40,
        created_at=utc_now() - timedelta(hours=2),
        started_at=utc_now() - timedelta(hours=2),
    )
    db_session.add(job)
    db_session.commit()

    data = _job(client, headers, stale_id)
    assert data["status"] == "failed"
    assert data["error_code"] == "JOB_TIMEOUT"
    assert data["error_message"] == "任务处理超时"


def test_stale_pending_job_reaped(client: TestClient, db_session: Session) -> None:
    """进程重启丢失的 pending 任务（created_at 超窗）读取时回收。"""
    headers = _auth(client)
    stale_id = "job_stale_pending"
    job = AsyncJob(
        job_id=stale_id,
        user_id=_user_id(client, headers),
        job_type="minutes_generate",
        resource_type="minutes",
        resource_id=None,
        status="pending",
        progress=0,
        created_at=utc_now() - timedelta(hours=2),
    )
    db_session.add(job)
    db_session.commit()

    data = _job(client, headers, stale_id)
    assert data["status"] == "failed"
    assert data["error_code"] == "JOB_TIMEOUT"


# ============================ 开关关闭时回退同步 ============================


def test_upload_falls_back_to_sync_when_async_disabled(
    client: TestClient, media_root
) -> None:
    """`ASYNC_JOBS_ENABLED=false`（conftest 默认）时保持原同步契约 201。"""
    headers = _auth(client)
    meeting = _meeting(client, headers)

    response = client.post(
        f"{MEETINGS}/{meeting['meeting_id']}/materials",
        files={"file": ("plan.txt", b"hello", "text/plain")},
        headers=headers,
    )

    assert response.status_code == 201, response.text
    data = response.json()["data"]
    assert data["processing_status"] == "processed"
    assert "job" not in data
