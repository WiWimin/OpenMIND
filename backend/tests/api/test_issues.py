import pytest
from fastapi.testclient import TestClient

from app.ai.extraction import IssueCandidate
from app.services import issue_service

REGISTER = "/api/v1/auth/register"
MEETINGS = "/api/v1/meetings"

PASSWORD = "secret123"


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


def _extract(client: TestClient, headers: dict[str, str], meeting_id: str) -> list[dict]:
    response = client.post(
        f"/api/v1/meetings/{meeting_id}/issues/extract",
        json={"record_ids": []},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]["items"]


@pytest.fixture()
def fake_extract(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        issue_service,
        "extract_candidates",
        lambda transcripts: [
            IssueCandidate(
                description="接口联调时间可能延期",
                follow_up="确认依赖接口完成时间",
                source_record_id=None,
            )
        ],
    )


def test_extract_issues(client: TestClient, fake_extract: None) -> None:
    headers = _auth(client)
    meeting = _meeting(client, headers)
    items = _extract(client, headers, meeting["meeting_id"])
    assert len(items) == 1
    issue = items[0]
    assert issue["issue_id"].startswith("iss_")
    assert issue["description"] == "接口联调时间可能延期"
    assert issue["status"] == "open"
    assert issue["follow_up"] == "确认依赖接口完成时间"
    assert issue["source"]["record_id"] is None


def test_extract_requires_auth(client: TestClient, fake_extract: None) -> None:
    response = client.post("/api/v1/meetings/mtg_x/issues/extract", json={})
    assert response.status_code == 401


def test_extract_meeting_not_found(client: TestClient, fake_extract: None) -> None:
    response = client.post(
        "/api/v1/meetings/mtg_missing/issues/extract", json={}, headers=_auth(client)
    )
    assert response.status_code == 404


def test_list_issues(client: TestClient, fake_extract: None) -> None:
    headers = _auth(client)
    meeting = _meeting(client, headers)
    _extract(client, headers, meeting["meeting_id"])
    _extract(client, headers, meeting["meeting_id"])

    response = client.get(
        f"/api/v1/meetings/{meeting['meeting_id']}/issues", headers=headers
    )
    assert response.status_code == 200
    assert response.json()["data"]["pagination"]["total"] == 2


def test_update_issue(client: TestClient, fake_extract: None) -> None:
    headers = _auth(client)
    meeting = _meeting(client, headers)
    issue = _extract(client, headers, meeting["meeting_id"])[0]

    response = client.patch(
        f"/api/v1/issues/{issue['issue_id']}",
        json={"status": "resolved", "follow_up": "已确认无风险"},
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "resolved"
    assert data["follow_up"] == "已确认无风险"


def test_update_cross_user_forbidden(client: TestClient, fake_extract: None) -> None:
    alice = _auth(client, "alice")
    meeting = _meeting(client, alice)
    issue = _extract(client, alice, meeting["meeting_id"])[0]
    bob = _auth(client, "bob")
    response = client.patch(
        f"/api/v1/issues/{issue['issue_id']}", json={"status": "cancelled"}, headers=bob
    )
    assert response.status_code == 404


def test_issue_update_validation(client: TestClient, fake_extract: None) -> None:
    headers = _auth(client)
    meeting = _meeting(client, headers)
    issue = _extract(client, headers, meeting["meeting_id"])[0]
    response = client.patch(
        f"/api/v1/issues/{issue['issue_id']}", json={"status": "bogus"}, headers=headers
    )
    assert response.status_code == 422


def test_meeting_delete_cascades_issues(client: TestClient, fake_extract: None) -> None:
    headers = _auth(client)
    meeting = _meeting(client, headers)
    _record(client, headers, meeting["meeting_id"])
    issue = _extract(client, headers, meeting["meeting_id"])[0]

    delete = client.delete(f"{MEETINGS}/{meeting['meeting_id']}", headers=headers)
    assert delete.status_code == 200

    gone = client.patch(
        f"/api/v1/issues/{issue['issue_id']}", json={"status": "resolved"}, headers=headers
    )
    assert gone.status_code == 404
