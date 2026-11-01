import pytest
from fastapi.testclient import TestClient

from app.ai.extraction import ActionItemCandidate
from app.core.config import get_settings
from app.services import action_item_service, audio_service, material_service, meeting_service

REGISTER = "/api/v1/auth/register"
MEETINGS = "/api/v1/meetings"

PASSWORD = "secret123"


@pytest.fixture()
def media_root(tmp_path, monkeypatch: pytest.MonkeyPatch):
    base = get_settings()

    def fake_settings():
        return base.model_copy(update={"storage_dir": str(tmp_path)})

    monkeypatch.setattr(material_service, "get_settings", fake_settings)
    monkeypatch.setattr(meeting_service, "get_settings", fake_settings)
    monkeypatch.setattr(audio_service, "get_settings", fake_settings)
    return tmp_path


@pytest.fixture()
def fake_extract(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        action_item_service,
        "extract_candidates",
        lambda transcripts, config=None: [ActionItemCandidate(content="完成接口联调")],
    )


def _auth(client: TestClient, name: str = "alice") -> dict[str, str]:
    token = client.post(
        REGISTER, json={"name": name, "password": PASSWORD}
    ).json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _meeting(client: TestClient, headers: dict[str, str]) -> dict:
    response = client.post(MEETINGS, json={"title": "周会"}, headers=headers)
    assert response.status_code == 201
    return response.json()["data"]


def _record(client: TestClient, headers: dict[str, str], meeting_id: str) -> dict:
    response = client.post(
        f"/api/v1/meetings/{meeting_id}/records", json={"content": "记录"}, headers=headers
    )
    assert response.status_code == 201
    return response.json()["data"]


def test_delete_meeting_cascades_children(
    client: TestClient, media_root
) -> None:
    headers = _auth(client)
    meeting = _meeting(client, headers)
    record = _record(client, headers, meeting["meeting_id"])

    upload = client.post(
        f"/api/v1/meetings/{meeting['meeting_id']}/materials",
        files={"file": ("a.txt", b"hello", "text/plain")},
        headers=headers,
    )
    assert upload.status_code == 201
    material = upload.json()["data"]
    material_path = media_root / "materials" / f"{material['material_id']}.txt"
    assert material_path.exists()

    response = client.delete(f"{MEETINGS}/{meeting['meeting_id']}", headers=headers)
    assert response.status_code == 200
    assert response.json()["data"] == {"deleted": True, "meeting_id": meeting["meeting_id"]}

    assert client.get(f"{MEETINGS}/{meeting['meeting_id']}", headers=headers).status_code == 404
    assert (
        client.patch(
            f"/api/v1/records/{record['record_id']}",
            json={"content": "x"},
            headers=headers,
        ).status_code
        == 404
    )
    assert (
        client.get(f"/api/v1/materials/{material['material_id']}", headers=headers).status_code
        == 404
    )
    assert not material_path.exists()


def test_delete_meeting_cascades_audio_files(
    client: TestClient, media_root, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        audio_service,
        "transcribe_file",
        lambda content, file_name: f"分段{file_name}",
    )
    headers = _auth(client)
    meeting = _meeting(client, headers)
    meeting_id = meeting["meeting_id"]

    # 实时会话：两片转写，finish 合并主文件
    started = client.post(
        f"/api/v1/meetings/{meeting_id}/audio/live/start",
        json={"file_type": "webm"},
        headers=headers,
    )
    assert started.status_code == 201
    audio_id = started.json()["data"]["audio_id"]
    for seq in (1, 2):
        chunk = client.post(
            f"/api/v1/audio/{audio_id}/live/chunk",
            files={"file": (f"chunk-{seq:04d}.webm", b"fake-audio", "audio/webm")},
            data={"seq": str(seq), "offset_seconds": str((seq - 1) * 30)},
            headers=headers,
        )
        assert chunk.status_code == 200
    finished = client.post(f"/api/v1/audio/{audio_id}/live/finish", headers=headers)
    assert finished.status_code == 200
    merged_path = media_root / "audio" / f"{audio_id}.webm"
    assert merged_path.exists()

    response = client.delete(f"{MEETINGS}/{meeting_id}", headers=headers)
    assert response.status_code == 200

    assert (
        client.get(f"/api/v1/audio/{audio_id}", headers=headers).status_code == 404
    )
    assert not merged_path.exists()
    chunks_dir = media_root / "audio" / audio_id
    assert not chunks_dir.exists() or not any(chunks_dir.iterdir())


def test_delete_meeting_blocked_by_converted_action(
    client: TestClient, fake_extract: None
) -> None:
    headers = _auth(client)
    meeting = _meeting(client, headers)
    _record(client, headers, meeting["meeting_id"])

    items = client.post(
        f"/api/v1/meetings/{meeting['meeting_id']}/action-items/extract",
        json={},
        headers=headers,
    ).json()["data"]["items"]
    action_id = items[0]["action_id"]
    client.post(f"/api/v1/action-items/{action_id}/confirm", headers=headers)
    client.post(
        f"/api/v1/action-items/{action_id}/convert-to-task",
        json={"title": "任务"},
        headers=headers,
    )

    response = client.delete(f"{MEETINGS}/{meeting['meeting_id']}", headers=headers)
    assert response.status_code == 409
    assert response.json()["error_code"] == "BUSINESS_RULE_VIOLATION"
    assert client.get(f"{MEETINGS}/{meeting['meeting_id']}", headers=headers).status_code == 200
