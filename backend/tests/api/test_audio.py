import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.services import audio_service

REGISTER = "/api/v1/auth/register"
MEETINGS = "/api/v1/meetings"
PASSWORD = "secret123"


@pytest.fixture()
def media_root(tmp_path, monkeypatch: pytest.MonkeyPatch):
    base = get_settings()

    def fake_settings():
        return base.model_copy(update={"storage_dir": str(tmp_path)})

    monkeypatch.setattr(audio_service, "get_settings", fake_settings)
    return tmp_path


@pytest.fixture()
def fake_transcription(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        audio_service,
        "transcribe_file",
        lambda content, file_name: "这是音频转写文本",
    )


def _auth(client: TestClient, name: str = "alice") -> dict[str, str]:
    token = client.post(
        REGISTER, json={"name": name, "password": PASSWORD}
    ).json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _meeting(client: TestClient, headers: dict[str, str]) -> dict:
    return client.post(MEETINGS, json={"title": "周会"}, headers=headers).json()["data"]


def _upload(
    client: TestClient,
    headers: dict[str, str],
    meeting_id: str,
    *,
    file_name: str = "meeting.mp3",
    content: bytes = b"fake-audio",
):
    return client.post(
        f"/api/v1/meetings/{meeting_id}/audio",
        files={"file": (file_name, content, "audio/mpeg")},
        headers=headers,
    )


def test_upload_transcribes_and_lists(
    client: TestClient, media_root, fake_transcription: None
) -> None:
    headers = _auth(client)
    meeting = _meeting(client, headers)

    uploaded = _upload(client, headers, meeting["meeting_id"])

    assert uploaded.status_code == 201, uploaded.text
    data = uploaded.json()["data"]
    assert data["audio_id"].startswith("aud_")
    assert data["status"] == "transcribed"
    assert data["transcript"] == "这是音频转写文本"
    assert data["record_id"] is None

    listing = client.get(
        f"/api/v1/meetings/{meeting['meeting_id']}/audio", headers=headers
    )
    assert listing.status_code == 200
    assert listing.json()["data"]["pagination"]["total"] == 1

    found = client.get(f"/api/v1/audio/{data['audio_id']}", headers=headers)
    assert found.status_code == 200
    assert found.json()["data"]["audio_id"] == data["audio_id"]


def test_update_and_confirm_creates_record(
    client: TestClient, media_root, fake_transcription: None
) -> None:
    headers = _auth(client)
    meeting = _meeting(client, headers)
    audio = _upload(client, headers, meeting["meeting_id"]).json()["data"]

    updated = client.patch(
        f"/api/v1/audio/{audio['audio_id']}",
        json={"transcript": "用户修订后的转写"},
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["transcript"] == "用户修订后的转写"

    confirmed = client.post(
        f"/api/v1/audio/{audio['audio_id']}/confirm", headers=headers
    )
    assert confirmed.status_code == 200
    data = confirmed.json()["data"]
    assert data["status"] == "confirmed"
    assert data["record_id"].startswith("rec_")

    records = client.get(
        f"/api/v1/meetings/{meeting['meeting_id']}/records", headers=headers
    ).json()["data"]["items"]
    assert any(
        item["record_id"] == data["record_id"]
        and item["content"] == "用户修订后的转写"
        and item["record_type"] == "transcript"
        for item in records
    )

    again = client.post(
        f"/api/v1/audio/{audio['audio_id']}/confirm", headers=headers
    )
    assert again.status_code == 200
    assert again.json()["data"]["record_id"] == data["record_id"]


def test_failed_transcription_can_retry(
    client: TestClient, media_root, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(content, file_name):
        raise AppError(
            "MODEL_TIMEOUT", "转写服务超时", http_status=504, retryable=True
        )

    monkeypatch.setattr(audio_service, "transcribe_file", fail)
    headers = _auth(client)
    meeting = _meeting(client, headers)
    audio = _upload(client, headers, meeting["meeting_id"]).json()["data"]

    assert audio["status"] == "failed"
    assert "超时" in audio["error"]

    monkeypatch.setattr(
        audio_service,
        "transcribe_file",
        lambda content, file_name: "重试成功",
    )
    retried = client.post(f"/api/v1/audio/{audio['audio_id']}/retry", headers=headers)

    assert retried.status_code == 200
    assert retried.json()["data"]["status"] == "transcribed"
    assert retried.json()["data"]["transcript"] == "重试成功"


def test_delete_unconfirmed_audio(
    client: TestClient, media_root, fake_transcription: None
) -> None:
    headers = _auth(client)
    meeting = _meeting(client, headers)
    audio = _upload(client, headers, meeting["meeting_id"]).json()["data"]

    deleted = client.delete(f"/api/v1/audio/{audio['audio_id']}", headers=headers)

    assert deleted.status_code == 200
    assert deleted.json()["data"] == {
        "deleted": True,
        "audio_id": audio["audio_id"],
    }
    assert client.get(f"/api/v1/audio/{audio['audio_id']}", headers=headers).status_code == 404


def test_confirmed_audio_cannot_be_deleted(
    client: TestClient, media_root, fake_transcription: None
) -> None:
    headers = _auth(client)
    meeting = _meeting(client, headers)
    audio = _upload(client, headers, meeting["meeting_id"]).json()["data"]
    client.post(f"/api/v1/audio/{audio['audio_id']}/confirm", headers=headers)

    deleted = client.delete(f"/api/v1/audio/{audio['audio_id']}", headers=headers)

    assert deleted.status_code == 409
    assert deleted.json()["error_code"] == "BUSINESS_RULE_VIOLATION"


def test_cross_user_audio_access_returns_404(
    client: TestClient, media_root, fake_transcription: None
) -> None:
    alice = _auth(client, "alice")
    meeting = _meeting(client, alice)
    audio = _upload(client, alice, meeting["meeting_id"]).json()["data"]
    bob = _auth(client, "bob")

    assert client.get(f"/api/v1/audio/{audio['audio_id']}", headers=bob).status_code == 404
    assert (
        client.post(f"/api/v1/audio/{audio['audio_id']}/retry", headers=bob).status_code
        == 404
    )
    assert (
        client.delete(f"/api/v1/audio/{audio['audio_id']}", headers=bob).status_code
        == 404
    )


def test_unsupported_audio_type(
    client: TestClient, media_root, fake_transcription: None
) -> None:
    headers = _auth(client)
    meeting = _meeting(client, headers)

    response = _upload(
        client,
        headers,
        meeting["meeting_id"],
        file_name="bad.exe",
        content=b"x",
    )

    assert response.status_code == 415
    assert response.json()["error_code"] == "FILE_TYPE_NOT_SUPPORTED"


def test_requires_auth(client: TestClient) -> None:
    assert client.get("/api/v1/meetings/mtg_x/audio").status_code == 401
    assert client.post("/api/v1/audio/aud_x/confirm").status_code == 401
