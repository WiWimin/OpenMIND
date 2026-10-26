from fastapi.testclient import TestClient

REGISTER = "/api/v1/auth/register"
MEETINGS = "/api/v1/meetings"

PASSWORD = "secret123"


def _auth(client: TestClient, name: str = "alice") -> dict[str, str]:
    response = client.post(REGISTER, json={"name": name, "password": PASSWORD})
    token = response.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _meeting(client: TestClient, headers: dict[str, str]) -> dict:
    response = client.post(MEETINGS, json={"title": "周会"}, headers=headers)
    assert response.status_code == 201
    return response.json()["data"]


def _create(
    client: TestClient,
    headers: dict[str, str],
    meeting_id: str,
    content: str = "讨论记录正文",
    record_type: str = "manual",
):
    return client.post(
        f"/api/v1/meetings/{meeting_id}/records",
        json={"content": content, "record_type": record_type},
        headers=headers,
    )


def test_create_record(client: TestClient) -> None:
    headers = _auth(client)
    meeting = _meeting(client, headers)
    response = _create(client, headers, meeting["meeting_id"])
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["record_id"].startswith("rec_")
    assert data["meeting_id"] == meeting["meeting_id"]
    assert data["content"] == "讨论记录正文"
    assert data["record_type"] == "manual"
    assert data["source_material_id"] is None


def test_create_record_with_marker(client: TestClient) -> None:
    headers = _auth(client)
    meeting = _meeting(client, headers)
    response = client.post(
        f"/api/v1/meetings/{meeting['meeting_id']}/records",
        json={"content": "决定周五上线", "marker_type": "decision"},
        headers=headers,
    )

    assert response.status_code == 201
    assert response.json()["data"]["marker_type"] == "decision"


def test_update_record_marker_and_clear(client: TestClient) -> None:
    headers = _auth(client)
    meeting = _meeting(client, headers)
    record = _create(client, headers, meeting["meeting_id"]).json()["data"]
    url = f"/api/v1/records/{record['record_id']}"

    marked = client.patch(url, json={"marker_type": "question"}, headers=headers)
    assert marked.status_code == 200
    assert marked.json()["data"]["marker_type"] == "question"

    cleared = client.patch(url, json={"marker_type": None}, headers=headers)
    assert cleared.status_code == 200
    assert cleared.json()["data"]["marker_type"] is None


def test_invalid_record_marker_rejected(client: TestClient) -> None:
    headers = _auth(client)
    meeting = _meeting(client, headers)
    response = client.post(
        f"/api/v1/meetings/{meeting['meeting_id']}/records",
        json={"content": "记录", "marker_type": "unknown"},
        headers=headers,
    )

    assert response.status_code == 422


def test_create_requires_auth(client: TestClient) -> None:
    response = client.post("/api/v1/meetings/mtg_x/records", json={"content": "x"})
    assert response.status_code == 401


def test_create_missing_content(client: TestClient) -> None:
    headers = _auth(client)
    meeting = _meeting(client, headers)
    response = client.post(
        f"/api/v1/meetings/{meeting['meeting_id']}/records", json={}, headers=headers
    )
    assert response.status_code == 422


def test_create_meeting_not_found(client: TestClient) -> None:
    response = _create(client, _auth(client), "mtg_missing")
    assert response.status_code == 404
    assert response.json()["error_code"] == "RESOURCE_NOT_FOUND"


def test_create_cross_user_forbidden(client: TestClient) -> None:
    alice = _auth(client, "alice")
    meeting = _meeting(client, alice)
    bob = _auth(client, "bob")
    assert _create(client, bob, meeting["meeting_id"]).status_code == 404


def test_list_records(client: TestClient) -> None:
    headers = _auth(client)
    meeting = _meeting(client, headers)
    _create(client, headers, meeting["meeting_id"], content="第一条")
    _create(client, headers, meeting["meeting_id"], content="第二条")

    response = client.get(
        f"/api/v1/meetings/{meeting['meeting_id']}/records", headers=headers
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["pagination"] == {"page": 1, "page_size": 20, "total": 2, "total_pages": 1}
    assert [item["content"] for item in data["items"]] == ["第一条", "第二条"]


def test_update_record(client: TestClient) -> None:
    headers = _auth(client)
    meeting = _meeting(client, headers)
    record = _create(client, headers, meeting["meeting_id"]).json()["data"]

    response = client.patch(
        f"/api/v1/records/{record['record_id']}",
        json={"content": "修改后的内容"},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["data"]["content"] == "修改后的内容"


def test_update_cross_user_forbidden(client: TestClient) -> None:
    alice = _auth(client, "alice")
    meeting = _meeting(client, alice)
    record = _create(client, alice, meeting["meeting_id"]).json()["data"]
    bob = _auth(client, "bob")
    response = client.patch(
        f"/api/v1/records/{record['record_id']}", json={"content": "越权"}, headers=bob
    )
    assert response.status_code == 404


def test_delete_record(client: TestClient) -> None:
    headers = _auth(client)
    meeting = _meeting(client, headers)
    record = _create(client, headers, meeting["meeting_id"]).json()["data"]
    url = f"/api/v1/records/{record['record_id']}"

    response = client.delete(url, headers=headers)
    assert response.status_code == 200
    assert response.json()["data"] == {"deleted": True, "record_id": record["record_id"]}

    bob = _auth(client, "bob")
    assert client.delete(url, headers=bob).status_code == 404
