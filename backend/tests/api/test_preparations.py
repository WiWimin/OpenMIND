import pytest
from fastapi.testclient import TestClient

from app.ai.preparation import PreparationDraft
from app.core.exceptions import AppError
from app.services import preparation_service

REGISTER = "/api/v1/auth/register"
MEETINGS = "/api/v1/meetings"

PASSWORD = "secret123"


@pytest.fixture()
def fake_draft(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake(meeting, snippets, user_goal):
        return PreparationDraft(summary="会议摘要", checklist=["确认里程碑", "排查风险"])

    monkeypatch.setattr(preparation_service, "generate_draft", fake)


def _auth(client: TestClient, name: str = "alice") -> dict[str, str]:
    response = client.post(REGISTER, json={"name": name, "password": PASSWORD})
    token = response.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _create_meeting(client: TestClient, headers: dict[str, str]) -> dict:
    response = client.post(MEETINGS, json={"title": "周会"}, headers=headers)
    assert response.status_code == 201
    return response.json()["data"]


def _generate(client: TestClient, headers: dict[str, str], meeting_id: str) -> dict:
    response = client.post(
        f"/api/v1/meetings/{meeting_id}/prepare",
        json={"include_history": True, "user_goal": "确认风险"},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


def test_generate_preparation(client: TestClient, fake_draft: None) -> None:
    headers = _auth(client)
    meeting = _create_meeting(client, headers)
    data = _generate(client, headers, meeting["meeting_id"])
    assert data["preparation_id"].startswith("prep_")
    assert data["meeting_id"] == meeting["meeting_id"]
    assert data["summary"] == "会议摘要"
    assert data["checklist"] == ["确认里程碑", "排查风险"]
    assert data["status"] == "draft"
    assert data["version"] == 1


def test_generate_requires_auth(client: TestClient, fake_draft: None) -> None:
    response = client.post("/api/v1/meetings/mtg_x/prepare", json={})
    assert response.status_code == 401


def test_generate_meeting_not_found(client: TestClient, fake_draft: None) -> None:
    response = client.post(
        "/api/v1/meetings/mtg_missing/prepare", json={}, headers=_auth(client)
    )
    assert response.status_code == 404
    assert response.json()["error_code"] == "RESOURCE_NOT_FOUND"


def test_generate_cross_user_forbidden(client: TestClient, fake_draft: None) -> None:
    alice = _auth(client, "alice")
    meeting = _create_meeting(client, alice)
    bob = _auth(client, "bob")
    response = client.post(
        f"/api/v1/meetings/{meeting['meeting_id']}/prepare", json={}, headers=bob
    )
    assert response.status_code == 404


def test_generate_ai_failure_propagates(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(meeting, snippets, user_goal):
        raise AppError("MODEL_TIMEOUT", "模型调用超时", http_status=504, retryable=True)

    monkeypatch.setattr(preparation_service, "generate_draft", boom)
    headers = _auth(client)
    meeting = _create_meeting(client, headers)
    response = client.post(
        f"/api/v1/meetings/{meeting['meeting_id']}/prepare", json={}, headers=headers
    )
    assert response.status_code == 504
    assert response.json()["error_code"] == "MODEL_TIMEOUT"
    assert response.json()["retryable"] is True


def test_list_preparations(client: TestClient, fake_draft: None) -> None:
    headers = _auth(client)
    meeting = _create_meeting(client, headers)
    _generate(client, headers, meeting["meeting_id"])
    _generate(client, headers, meeting["meeting_id"])

    response = client.get(
        f"/api/v1/meetings/{meeting['meeting_id']}/preparations", headers=headers
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["pagination"] == {"page": 1, "page_size": 20, "total": 2, "total_pages": 1}
    assert len(data["items"]) == 2


def test_get_preparation_and_cross_user(client: TestClient, fake_draft: None) -> None:
    alice = _auth(client, "alice")
    meeting = _create_meeting(client, alice)
    preparation = _generate(client, alice, meeting["meeting_id"])
    url = f"/api/v1/preparations/{preparation['preparation_id']}"

    found = client.get(url, headers=alice)
    assert found.status_code == 200
    assert found.json()["data"]["preparation_id"] == preparation["preparation_id"]

    bob = _auth(client, "bob")
    assert client.get(url, headers=bob).status_code == 404
    assert client.patch(url, json={"summary": "越权"}, headers=bob).status_code == 404


def test_update_preparation_increments_version(client: TestClient, fake_draft: None) -> None:
    headers = _auth(client)
    meeting = _create_meeting(client, headers)
    preparation = _generate(client, headers, meeting["meeting_id"])

    response = client.patch(
        f"/api/v1/preparations/{preparation['preparation_id']}",
        json={"summary": "更新后的摘要", "checklist": ["仅一项"]},
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["summary"] == "更新后的摘要"
    assert data["checklist"] == ["仅一项"]
    assert data["version"] == 2


def test_confirm_preparation(client: TestClient, fake_draft: None) -> None:
    headers = _auth(client)
    meeting = _create_meeting(client, headers)
    preparation = _generate(client, headers, meeting["meeting_id"])

    response = client.post(
        f"/api/v1/preparations/{preparation['preparation_id']}/confirm", headers=headers
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["status"] == "confirmed"
    assert data["version"] == 1


def test_confirm_preparation_is_idempotent(client: TestClient, fake_draft: None) -> None:
    headers = _auth(client)
    meeting = _create_meeting(client, headers)
    preparation = _generate(client, headers, meeting["meeting_id"])
    url = f"/api/v1/preparations/{preparation['preparation_id']}/confirm"

    first = client.post(url, headers=headers)
    assert first.status_code == 200
    second = client.post(url, headers=headers)
    assert second.status_code == 200
    data = second.json()["data"]
    assert data["status"] == "confirmed"
    assert data["version"] == 1


def test_confirm_preparation_cross_user_forbidden(
    client: TestClient, fake_draft: None
) -> None:
    alice = _auth(client, "alice")
    meeting = _create_meeting(client, alice)
    preparation = _generate(client, alice, meeting["meeting_id"])
    bob = _auth(client, "bob")

    response = client.post(
        f"/api/v1/preparations/{preparation['preparation_id']}/confirm", headers=bob
    )
    assert response.status_code == 404


def test_confirm_preparation_requires_auth(client: TestClient, fake_draft: None) -> None:
    response = client.post("/api/v1/preparations/prep_x/confirm")
    assert response.status_code == 401
