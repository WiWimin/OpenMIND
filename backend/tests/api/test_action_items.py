import pytest
from fastapi.testclient import TestClient

from app.ai.extraction import ActionItemCandidate
from app.services import action_item_service

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


def _record(
    client: TestClient, headers: dict[str, str], meeting_id: str
) -> dict:
    response = client.post(
        f"/api/v1/meetings/{meeting_id}/records",
        json={"content": "张三负责下周一前完成接口联调"},
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()["data"]


def _extract(
    client: TestClient, headers: dict[str, str], meeting_id: str
) -> list[dict]:
    response = client.post(
        f"/api/v1/meetings/{meeting_id}/action-items/extract",
        json={"record_ids": []},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]["items"]


@pytest.fixture()
def fake_extract(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        action_item_service,
        "extract_candidates",
        lambda transcripts, config=None: [
            ActionItemCandidate(
                content="完成接口联调",
                assignee="张三",
                due_date="2026-10-05",
                source_record_id=None,
                source_excerpt="张三负责下周一前完成",
            )
        ],
    )


def test_extract_action_items(client: TestClient, fake_extract: None) -> None:
    headers = _auth(client)
    meeting = _meeting(client, headers)
    _record(client, headers, meeting["meeting_id"])
    items = _extract(client, headers, meeting["meeting_id"])
    assert len(items) == 1
    item = items[0]
    assert item["action_id"].startswith("act_")
    assert item["content"] == "完成接口联调"
    assert item["assignee"] == "张三"
    assert item["due_date"] == "2026-10-05"
    assert item["status"] == "pending_confirmation"
    assert item["source"]["excerpt"] == "张三负责下周一前完成"


def test_extract_requires_auth(client: TestClient, fake_extract: None) -> None:
    response = client.post("/api/v1/meetings/mtg_x/action-items/extract", json={})
    assert response.status_code == 401


def test_extract_meeting_not_found(client: TestClient, fake_extract: None) -> None:
    response = client.post(
        "/api/v1/meetings/mtg_missing/action-items/extract", json={}, headers=_auth(client)
    )
    assert response.status_code == 404


def test_list_action_items(client: TestClient, fake_extract: None) -> None:
    headers = _auth(client)
    meeting = _meeting(client, headers)
    _extract(client, headers, meeting["meeting_id"])
    _extract(client, headers, meeting["meeting_id"])

    response = client.get(
        f"/api/v1/meetings/{meeting['meeting_id']}/action-items", headers=headers
    )
    assert response.status_code == 200
    assert response.json()["data"]["pagination"]["total"] == 2


def test_update_action_item(client: TestClient, fake_extract: None) -> None:
    headers = _auth(client)
    meeting = _meeting(client, headers)
    action = _extract(client, headers, meeting["meeting_id"])[0]

    response = client.patch(
        f"/api/v1/action-items/{action['action_id']}",
        json={"content": "更新后的内容", "assignee": "李四", "due_date": "2026-10-10"},
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["content"] == "更新后的内容"
    assert data["assignee"] == "李四"
    assert data["due_date"] == "2026-10-10"


def test_get_and_cross_user(client: TestClient, fake_extract: None) -> None:
    alice = _auth(client, "alice")
    meeting = _meeting(client, alice)
    action = _extract(client, alice, meeting["meeting_id"])[0]
    url = f"/api/v1/action-items/{action['action_id']}"

    assert client.get(url, headers=alice).status_code == 200
    bob = _auth(client, "bob")
    assert client.get(url, headers=bob).status_code == 404
    assert client.post(f"{url}/confirm", headers=bob).status_code == 404


def test_confirm_action_item(client: TestClient, fake_extract: None) -> None:
    headers = _auth(client)
    meeting = _meeting(client, headers)
    action = _extract(client, headers, meeting["meeting_id"])[0]

    response = client.post(f"/api/v1/action-items/{action['action_id']}/confirm", headers=headers)
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "confirmed"


def test_delete_action_item(client: TestClient, fake_extract: None) -> None:
    headers = _auth(client)
    meeting = _meeting(client, headers)
    action = _extract(client, headers, meeting["meeting_id"])[0]
    url = f"/api/v1/action-items/{action['action_id']}"

    response = client.delete(url, headers=headers)
    assert response.status_code == 200
    assert response.json()["data"] == {"deleted": True, "action_id": action["action_id"]}
    assert client.get(url, headers=headers).status_code == 404


def test_convert_to_task_and_idempotent(client: TestClient, fake_extract: None) -> None:
    headers = _auth(client)
    meeting = _meeting(client, headers)
    action = _extract(client, headers, meeting["meeting_id"])[0]
    action_url = f"/api/v1/action-items/{action['action_id']}"
    client.post(f"{action_url}/confirm", headers=headers)

    first = client.post(
        f"{action_url}/convert-to-task",
        json={"title": "完成接口联调", "due_date": "2026-10-05"},
        headers=headers,
    )
    assert first.status_code == 201
    task = first.json()["data"]
    assert task["task_id"].startswith("tsk_")
    assert task["action_id"] == action["action_id"]
    assert task["status"] == "todo"
    assert task["meeting_id"] == meeting["meeting_id"]

    assert client.get(action_url, headers=headers).json()["data"]["status"] == "converted"

    second = client.post(
        f"{action_url}/convert-to-task",
        json={"title": "完成接口联调"},
        headers=headers,
    )
    assert second.status_code == 200
    assert second.json()["data"]["task_id"] == task["task_id"]


def test_convert_requires_confirmed(client: TestClient, fake_extract: None) -> None:
    headers = _auth(client)
    meeting = _meeting(client, headers)
    action = _extract(client, headers, meeting["meeting_id"])[0]

    response = client.post(
        f"/api/v1/action-items/{action['action_id']}/convert-to-task",
        json={"title": "未确认不可转"},
        headers=headers,
    )
    assert response.status_code == 409
    assert response.json()["error_code"] == "BUSINESS_RULE_VIOLATION"


def test_delete_converted_action_conflict(client: TestClient, fake_extract: None) -> None:
    headers = _auth(client)
    meeting = _meeting(client, headers)
    action = _extract(client, headers, meeting["meeting_id"])[0]
    action_url = f"/api/v1/action-items/{action['action_id']}"
    client.post(f"{action_url}/confirm", headers=headers)
    client.post(f"{action_url}/convert-to-task", json={"title": "任务"}, headers=headers)

    response = client.delete(action_url, headers=headers)
    assert response.status_code == 409


def test_extract_discards_unknown_source_record(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers = _auth(client)
    meeting = _meeting(client, headers)
    _record(client, headers, meeting["meeting_id"])
    monkeypatch.setattr(
        action_item_service,
        "extract_candidates",
        lambda transcripts, config=None: [
            ActionItemCandidate(content="行动项", source_record_id="rec_missing")
        ],
    )

    item = _extract(client, headers, meeting["meeting_id"])[0]

    assert item["source"]["record_id"] is None


def test_extract_keeps_valid_source_record(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers = _auth(client)
    meeting = _meeting(client, headers)
    record = _record(client, headers, meeting["meeting_id"])
    monkeypatch.setattr(
        action_item_service,
        "extract_candidates",
        lambda transcripts, config=None: [
            ActionItemCandidate(
                content="行动项",
                source_record_id=record["record_id"],
                source_excerpt="张三负责",
            )
        ],
    )

    item = _extract(client, headers, meeting["meeting_id"])[0]

    assert item["source"]["record_id"] == record["record_id"]
    assert item["source"]["excerpt"] == "张三负责"


def test_delete_record_referenced_by_action_conflict(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers = _auth(client)
    meeting = _meeting(client, headers)
    record = _record(client, headers, meeting["meeting_id"])
    monkeypatch.setattr(
        action_item_service,
        "extract_candidates",
        lambda transcripts, config=None: [
            ActionItemCandidate(
                content="行动项",
                source_record_id=record["record_id"],
            )
        ],
    )
    _extract(client, headers, meeting["meeting_id"])

    response = client.delete(f"/api/v1/records/{record['record_id']}", headers=headers)

    assert response.status_code == 409
    assert response.json()["error_code"] == "BUSINESS_RULE_VIOLATION"
