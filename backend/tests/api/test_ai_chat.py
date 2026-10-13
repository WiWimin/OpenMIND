import pytest
from fastapi.testclient import TestClient

from app.ai.chat import ChatAnswer, Source
from app.services import ai_chat_service

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


def _record(client: TestClient, headers: dict[str, str], meeting_id: str) -> dict:
    response = client.post(
        f"/api/v1/meetings/{meeting_id}/records",
        json={"content": "讨论记录正文"},
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()["data"]


def test_chat_insufficient_evidence(client: TestClient) -> None:
    headers = _auth(client)
    meeting = _meeting(client, headers)
    response = client.post(
        f"/api/v1/meetings/{meeting['meeting_id']}/chat",
        json={"question": "上次会议决定了什么？"},
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["insufficient_evidence"] is True
    assert data["sources"] == []


def test_chat_requires_auth(client: TestClient) -> None:
    response = client.post("/api/v1/meetings/mtg_x/chat", json={"question": "?"})
    assert response.status_code == 401


def test_chat_meeting_not_found(client: TestClient) -> None:
    response = client.post(
        "/api/v1/meetings/mtg_missing/chat", json={"question": "?"}, headers=_auth(client)
    )
    assert response.status_code == 404


def test_chat_with_sources(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeChat:
        def answer(self, question, *, user_id, scope, current_meeting_id):
            return ChatAnswer(
                answer="根据材料，结论是……",
                sources=[Source("mtg_old", "mat_old", None, "相关原文片段")],
                insufficient_evidence=False,
            )

    monkeypatch.setattr(ai_chat_service, "_chat_service", lambda db, user_id: FakeChat())

    headers = _auth(client)
    meeting = _meeting(client, headers)
    response = client.post(
        f"/api/v1/meetings/{meeting['meeting_id']}/chat",
        json={"question": "结论是什么？", "include_sources": True},
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["answer"] == "根据材料，结论是……"
    assert data["insufficient_evidence"] is False
    assert data["sources"] == [
        {
            "meeting_id": "mtg_old",
            "material_id": "mat_old",
            "record_id": None,
            "excerpt": "相关原文片段",
        }
    ]


def test_chat_include_sources_false(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeChat:
        def answer(self, question, *, user_id, scope, current_meeting_id):
            return ChatAnswer(
                answer="答案",
                sources=[Source("mtg_old", "mat_old", None, "片段")],
                insufficient_evidence=False,
            )

    monkeypatch.setattr(ai_chat_service, "_chat_service", lambda db, user_id: FakeChat())
    headers = _auth(client)
    meeting = _meeting(client, headers)
    response = client.post(
        f"/api/v1/meetings/{meeting['meeting_id']}/chat",
        json={"question": "q", "include_sources": False},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["data"]["sources"] == []


def test_chat_cross_user_forbidden(client: TestClient) -> None:
    alice = _auth(client, "alice")
    meeting = _meeting(client, alice)
    bob = _auth(client, "bob")
    response = client.post(
        f"/api/v1/meetings/{meeting['meeting_id']}/chat",
        json={"question": "?"},
        headers=bob,
    )
    assert response.status_code == 404


def test_organize_records(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        ai_chat_service, "_organize_text", lambda transcripts, style: "整理后的内容"
    )
    headers = _auth(client)
    meeting = _meeting(client, headers)
    record = _record(client, headers, meeting["meeting_id"])

    response = client.post(
        f"/api/v1/meetings/{meeting['meeting_id']}/organize",
        json={"record_ids": [record["record_id"]], "style": "structured"},
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["organized_content"] == "整理后的内容"
    assert data["source_record_ids"] == [record["record_id"]]


def test_organize_no_matching_records(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        ai_chat_service, "_organize_text", lambda transcripts, style: "不应被调用"
    )
    headers = _auth(client)
    meeting = _meeting(client, headers)
    response = client.post(
        f"/api/v1/meetings/{meeting['meeting_id']}/organize",
        json={"record_ids": ["rec_missing"]},
        headers=headers,
    )
    assert response.status_code == 422
    assert response.json()["error_code"] == "VALIDATION_ERROR"


def test_organize_cross_user_forbidden(client: TestClient) -> None:
    alice = _auth(client, "alice")
    meeting = _meeting(client, alice)
    record = _record(client, alice, meeting["meeting_id"])
    bob = _auth(client, "bob")
    response = client.post(
        f"/api/v1/meetings/{meeting['meeting_id']}/organize",
        json={"record_ids": [record["record_id"]]},
        headers=bob,
    )
    assert response.status_code == 404
