import pytest
from fastapi.testclient import TestClient

from app.ai.chat import ChatAnswer
from app.ai.extraction import ActionItemCandidate, IssueCandidate
from app.ai.preparation import PreparationDraft
from app.core.config import get_settings
from app.services import (
    action_item_service,
    ai_chat_service,
    issue_service,
    material_service,
    meeting_service,
    minutes_service,
    preparation_service,
)

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
def fake_ai(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        preparation_service,
        "generate_draft",
        lambda meeting, snippets, user_goal, config=None: PreparationDraft(
            summary="摘要", checklist=[]
        ),
    )
    monkeypatch.setattr(
        minutes_service, "generate_text", lambda meeting, transcripts, config=None: "纪要"
    )
    monkeypatch.setattr(
        action_item_service,
        "extract_candidates",
        lambda transcripts, config=None: [ActionItemCandidate(content="行动项")],
    )
    monkeypatch.setattr(
        issue_service,
        "extract_candidates",
        lambda transcripts, config=None: [IssueCandidate(description="问题")],
    )
    monkeypatch.setattr(
        ai_chat_service,
        "_chat_service",
        lambda db, user_id: type(
            "FakeChat",
            (),
            {
                "answer": lambda self, *args, **kwargs: ChatAnswer(
                    answer="无法确认", sources=[], insufficient_evidence=True
                )
            },
        )(),
    )


def _auth(client: TestClient) -> dict[str, str]:
    token = client.post(
        REGISTER, json={"name": "archived-user", "password": PASSWORD}
    ).json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _create_meeting(client: TestClient, headers: dict[str, str]) -> str:
    response = client.post(MEETINGS, json={"title": "归档只读测试"}, headers=headers)
    assert response.status_code == 201
    return response.json()["data"]["meeting_id"]


def test_archived_meeting_rejects_all_mutations(
    client: TestClient, media_root, fake_ai: None
) -> None:
    headers = _auth(client)
    meeting_id = _create_meeting(client, headers)

    material = client.post(
        f"/api/v1/meetings/{meeting_id}/materials",
        files={"file": ("a.txt", b"material", "text/plain")},
        headers=headers,
    ).json()["data"]
    record = client.post(
        f"/api/v1/meetings/{meeting_id}/records",
        json={"content": "记录"},
        headers=headers,
    ).json()["data"]
    preparation = client.post(
        f"/api/v1/meetings/{meeting_id}/prepare", json={}, headers=headers
    ).json()["data"]
    minutes = client.post(
        f"/api/v1/meetings/{meeting_id}/minutes/generate",
        json={"record_ids": [record["record_id"]]},
        headers=headers,
    ).json()["data"]
    action = client.post(
        f"/api/v1/meetings/{meeting_id}/action-items/extract",
        json={},
        headers=headers,
    ).json()["data"]["items"][0]
    issue = client.post(
        f"/api/v1/meetings/{meeting_id}/issues/extract",
        json={},
        headers=headers,
    ).json()["data"]["items"][0]

    archived = client.post(f"/api/v1/meetings/{meeting_id}/archive", headers=headers)
    assert archived.status_code == 200

    mutations = [
        client.patch(f"{MEETINGS}/{meeting_id}", json={"title": "x"}, headers=headers),
        client.post(
            f"/api/v1/meetings/{meeting_id}/materials",
            files={"file": ("b.txt", b"material", "text/plain")},
            headers=headers,
        ),
        client.delete(f"/api/v1/materials/{material['material_id']}", headers=headers),
        client.post(
            f"/api/v1/meetings/{meeting_id}/records",
            json={"content": "新记录"},
            headers=headers,
        ),
        client.patch(
            f"/api/v1/records/{record['record_id']}",
            json={"content": "修改"},
            headers=headers,
        ),
        client.delete(f"/api/v1/records/{record['record_id']}", headers=headers),
        client.post(f"/api/v1/meetings/{meeting_id}/prepare", json={}, headers=headers),
        client.patch(
            f"/api/v1/preparations/{preparation['preparation_id']}",
            json={"summary": "修改"},
            headers=headers,
        ),
        client.post(
            f"/api/v1/preparations/{preparation['preparation_id']}/confirm",
            headers=headers,
        ),
        client.post(
            f"/api/v1/meetings/{meeting_id}/chat",
            json={"question": "?"},
            headers=headers,
        ),
        client.post(
            f"/api/v1/meetings/{meeting_id}/organize",
            json={"record_ids": [record["record_id"]]},
            headers=headers,
        ),
        client.post(
            f"/api/v1/meetings/{meeting_id}/minutes/generate",
            json={"record_ids": [record["record_id"]]},
            headers=headers,
        ),
        client.patch(
            f"/api/v1/minutes/{minutes['minutes_id']}",
            json={"content": "修改"},
            headers=headers,
        ),
        client.post(
            f"/api/v1/minutes/{minutes['minutes_id']}/confirm", headers=headers
        ),
        client.post(
            f"/api/v1/meetings/{meeting_id}/action-items/extract",
            json={},
            headers=headers,
        ),
        client.patch(
            f"/api/v1/action-items/{action['action_id']}",
            json={"content": "修改"},
            headers=headers,
        ),
        client.post(
            f"/api/v1/action-items/{action['action_id']}/confirm", headers=headers
        ),
        client.post(
            f"/api/v1/action-items/{action['action_id']}/convert-to-task",
            json={"title": "任务"},
            headers=headers,
        ),
        client.delete(
            f"/api/v1/action-items/{action['action_id']}", headers=headers
        ),
        client.post(
            f"/api/v1/meetings/{meeting_id}/issues/extract", json={}, headers=headers
        ),
        client.patch(
            f"/api/v1/issues/{issue['issue_id']}",
            json={"status": "resolved"},
            headers=headers,
        ),
    ]

    for response in mutations:
        assert response.status_code == 409, response.text
        assert response.json()["error_code"] == "BUSINESS_RULE_VIOLATION"

    assert client.get(f"{MEETINGS}/{meeting_id}", headers=headers).status_code == 200
    assert (
        client.get(f"/api/v1/meetings/{meeting_id}/materials", headers=headers).status_code
        == 200
    )
    assert (
        client.get(f"/api/v1/meetings/{meeting_id}/records", headers=headers).status_code
        == 200
    )
