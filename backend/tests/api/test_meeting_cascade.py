import pytest
from fastapi.testclient import TestClient

from app.ai.extraction import ActionItemCandidate
from app.core.config import get_settings
from app.services import action_item_service, material_service, meeting_service

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
    return tmp_path


@pytest.fixture()
def fake_extract(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        action_item_service,
        "extract_candidates",
        lambda transcripts: [ActionItemCandidate(content="完成接口联调")],
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
