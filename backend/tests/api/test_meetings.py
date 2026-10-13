from fastapi.testclient import TestClient

REGISTER = "/api/v1/auth/register"
MEETINGS = "/api/v1/meetings"

PASSWORD = "secret123"


def _auth(client: TestClient, name: str = "alice") -> dict[str, str]:
    response = client.post(REGISTER, json={"name": name, "password": PASSWORD})
    token = response.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _create(client: TestClient, headers: dict[str, str], **overrides: object) -> dict:
    payload: dict[str, object] = {"title": "项目周会"}
    payload.update(overrides)
    response = client.post(MEETINGS, json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["data"]


def test_create_meeting(client: TestClient) -> None:
    headers = _auth(client)
    data = _create(
        client,
        headers,
        title="项目周会",
        topic="进度与风险",
        meeting_time="2026-10-02T14:00:00+08:00",
    )
    assert data["title"] == "项目周会"
    assert data["topic"] == "进度与风险"
    assert data["status"] == "scheduled"
    assert data["archived_at"] is None
    assert data["meeting_id"].startswith("mtg_")
    assert "user_id" not in data


def test_create_requires_auth(client: TestClient) -> None:
    response = client.post(MEETINGS, json={"title": "未登录"})
    assert response.status_code == 401
    assert response.json()["error_code"] == "AUTH_REQUIRED"


def test_create_missing_title(client: TestClient) -> None:
    response = client.post(MEETINGS, json={}, headers=_auth(client))
    assert response.status_code == 422
    assert response.json()["error_code"] == "VALIDATION_ERROR"


def test_list_pagination_and_status_filter(client: TestClient) -> None:
    headers = _auth(client)
    _create(client, headers, title="A")
    _create(client, headers, title="B")

    listing = client.get(MEETINGS, headers=headers).json()["data"]
    assert listing["pagination"] == {
        "page": 1,
        "page_size": 20,
        "total": 2,
        "total_pages": 1,
    }
    assert len(listing["items"]) == 2

    scheduled = client.get(MEETINGS, params={"status": "scheduled"}, headers=headers).json()
    assert scheduled["data"]["pagination"]["total"] == 2

    archived = client.get(MEETINGS, params={"status": "archived"}, headers=headers).json()
    assert archived["data"]["pagination"]["total"] == 0


def test_list_page_size_upper_bound(client: TestClient) -> None:
    response = client.get(MEETINGS, params={"page_size": 200}, headers=_auth(client))
    assert response.status_code == 422


def test_get_meeting_and_not_found(client: TestClient) -> None:
    headers = _auth(client)
    meeting = _create(client, headers)

    found = client.get(f"{MEETINGS}/{meeting['meeting_id']}", headers=headers)
    assert found.status_code == 200
    assert found.json()["data"]["meeting_id"] == meeting["meeting_id"]

    missing = client.get(f"{MEETINGS}/mtg_missing", headers=headers)
    assert missing.status_code == 404
    assert missing.json()["error_code"] == "RESOURCE_NOT_FOUND"


def test_cross_user_isolation(client: TestClient) -> None:
    alice = _auth(client, "alice")
    meeting = _create(client, alice)
    bob = _auth(client, "bob")
    url = f"{MEETINGS}/{meeting['meeting_id']}"

    assert client.get(url, headers=bob).status_code == 404
    assert client.patch(url, json={"title": "越权"}, headers=bob).status_code == 404
    assert client.delete(url, headers=bob).status_code == 404
    assert client.post(f"{url}/archive", headers=bob).status_code == 404

    bob_list = client.get(MEETINGS, headers=bob).json()["data"]
    assert bob_list["pagination"]["total"] == 0


def test_update_meeting(client: TestClient) -> None:
    headers = _auth(client)
    meeting = _create(client, headers)
    response = client.patch(
        f"{MEETINGS}/{meeting['meeting_id']}",
        json={"title": "新标题", "topic": "新主题"},
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["title"] == "新标题"
    assert data["topic"] == "新主题"


def test_update_null_title_rejected(client: TestClient) -> None:
    headers = _auth(client)
    meeting = _create(client, headers)
    response = client.patch(
        f"{MEETINGS}/{meeting['meeting_id']}", json={"title": None}, headers=headers
    )
    assert response.status_code == 422
    assert response.json()["error_code"] == "VALIDATION_ERROR"


def test_archive_sets_fields_and_is_idempotent(client: TestClient) -> None:
    headers = _auth(client)
    meeting = _create(client, headers)
    url = f"{MEETINGS}/{meeting['meeting_id']}/archive"

    first = client.post(url, headers=headers)
    assert first.status_code == 200
    data = first.json()["data"]
    assert data["status"] == "archived"
    assert data["archived_at"] is not None

    second = client.post(url, headers=headers)
    assert second.status_code == 200
    assert second.json()["data"]["status"] == "archived"


def test_update_archived_meeting_conflict(client: TestClient) -> None:
    headers = _auth(client)
    meeting = _create(client, headers)
    client.post(f"{MEETINGS}/{meeting['meeting_id']}/archive", headers=headers)

    response = client.patch(
        f"{MEETINGS}/{meeting['meeting_id']}", json={"title": "尝试编辑"}, headers=headers
    )
    assert response.status_code == 409
    assert response.json()["error_code"] == "BUSINESS_RULE_VIOLATION"


def test_delete_meeting(client: TestClient) -> None:
    headers = _auth(client)
    meeting = _create(client, headers)
    url = f"{MEETINGS}/{meeting['meeting_id']}"

    response = client.delete(url, headers=headers)
    assert response.status_code == 200
    assert response.json()["data"] == {"deleted": True, "meeting_id": meeting["meeting_id"]}
    assert client.get(url, headers=headers).status_code == 404
