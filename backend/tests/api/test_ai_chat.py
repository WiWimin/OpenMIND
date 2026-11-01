import pytest
from fastapi.testclient import TestClient

from app.ai.chat import ChatAnswer, Source
from app.schemas.chat import ChatContextScope, ChatRequest
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


def test_chat_request_defaults_to_current_meeting() -> None:
    assert ChatRequest(question="?").context_scope == ChatContextScope.current_meeting


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
        def answer(self, question, *, user_id, scope, current_meeting_id, records=None, **kwargs):
            return ChatAnswer(
                answer="根据材料，结论是……",
                sources=[Source("mtg_old", "mat_old", None, "相关原文片段")],
                insufficient_evidence=False,
            )

    monkeypatch.setattr(
        ai_chat_service, "_chat_service", lambda db, user_id, model=None: FakeChat()
    )

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
            "document_id": None,
            "document_name": None,
            "excerpt": "相关原文片段",
        }
    ]


def test_chat_include_sources_false(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeChat:
        def answer(self, question, *, user_id, scope, current_meeting_id, records=None, **kwargs):
            return ChatAnswer(
                answer="答案",
                sources=[Source("mtg_old", "mat_old", None, "片段")],
                insufficient_evidence=False,
            )

    monkeypatch.setattr(
        ai_chat_service, "_chat_service", lambda db, user_id, model=None: FakeChat()
    )
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
        ai_chat_service, "_run_organize_llm", lambda messages, config=None: "整理后的内容"
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
    assert data["task"] == "organize"
    assert data["organized_content"] == "整理后的内容"
    assert data["structured"] is None
    assert data["source_record_ids"] == [record["record_id"]]


def test_organize_no_matching_records(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(messages, config=None):
        raise AssertionError("不应调用 LLM")

    monkeypatch.setattr(ai_chat_service, "_run_organize_llm", fail)
    headers = _auth(client)
    meeting = _meeting(client, headers)
    response = client.post(
        f"/api/v1/meetings/{meeting['meeting_id']}/organize",
        json={"record_ids": ["rec_missing"]},
        headers=headers,
    )
    assert response.status_code == 422
    assert response.json()["error_code"] == "VALIDATION_ERROR"


def test_organize_unknown_task_rejected(client: TestClient) -> None:
    headers = _auth(client)
    meeting = _meeting(client, headers)
    response = client.post(
        f"/api/v1/meetings/{meeting['meeting_id']}/organize",
        json={"task": "agenda"},
        headers=headers,
    )
    assert response.status_code == 422


def test_organize_summary_returns_structured(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    raw = (
        "```json\n"
        '{"conclusion": ["确定上线时间"], "key_discussions": [], '
        '"action_items": [{"task": "准备发布文案", "assignee": "李四", '
        '"deadline": null, "priority": "high", "source_quote": "李四准备发布文案"}], '
        '"open_questions": []}'
        "\n```"
    )
    monkeypatch.setattr(
        ai_chat_service, "_run_organize_llm", lambda messages, config=None: raw
    )
    headers = _auth(client)
    meeting = _meeting(client, headers)
    _record(client, headers, meeting["meeting_id"])

    response = client.post(
        f"/api/v1/meetings/{meeting['meeting_id']}/organize",
        json={"task": "summary"},
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["task"] == "summary"
    assert data["organized_content"] == ""
    assert data["structured"]["conclusion"] == ["确定上线时间"]
    assert data["structured"]["action_items"][0]["task"] == "准备发布文案"


def test_organize_summary_without_action_items(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    # 幻觉防护：纯讨论内容 → action_items 必须为空数组
    raw = (
        '{"conclusion": [], "key_discussions": [{"topic": "方向讨论", "points": ["A", "B"]}], '
        '"action_items": [], "open_questions": ["排期何时确定"]}'
    )
    monkeypatch.setattr(
        ai_chat_service, "_run_organize_llm", lambda messages, config=None: raw
    )
    headers = _auth(client)
    meeting = _meeting(client, headers)
    _record(client, headers, meeting["meeting_id"])

    response = client.post(
        f"/api/v1/meetings/{meeting['meeting_id']}/organize",
        json={"task": "summary"},
        headers=headers,
    )
    assert response.status_code == 200
    structured = response.json()["data"]["structured"]
    assert structured["action_items"] == []
    assert structured["open_questions"] == ["排期何时确定"]


def test_organize_structured_fallback_on_unparseable(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        ai_chat_service,
        "_run_organize_llm",
        lambda messages, config=None: "抱歉，我无法完成该任务。",
    )
    headers = _auth(client)
    meeting = _meeting(client, headers)
    _record(client, headers, meeting["meeting_id"])

    response = client.post(
        f"/api/v1/meetings/{meeting['meeting_id']}/organize",
        json={"task": "summary"},
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["structured"] is None
    assert "抱歉" in data["organized_content"]


def test_organize_polish_empty_result(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    # 通顺文本 → 输出空数组，而不是硬找问题
    monkeypatch.setattr(
        ai_chat_service, "_run_organize_llm", lambda messages, config=None: "[]"
    )
    headers = _auth(client)
    meeting = _meeting(client, headers)
    _record(client, headers, meeting["meeting_id"])

    response = client.post(
        f"/api/v1/meetings/{meeting['meeting_id']}/organize",
        json={"task": "polish"},
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["task"] == "polish"
    assert data["structured"] == []
    assert data["organized_content"] == ""


def test_organize_text_takes_priority(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, db_session
) -> None:
    captured: dict[str, str] = {}

    def fake_llm(messages, config=None):
        captured["user"] = messages[-1]["content"]
        return "基于选中内容的整理"

    monkeypatch.setattr(ai_chat_service, "_run_organize_llm", fake_llm)
    headers = _auth(client)
    meeting = _meeting(client, headers)
    record = _record(client, headers, meeting["meeting_id"])

    response = client.post(
        f"/api/v1/meetings/{meeting['meeting_id']}/organize",
        json={"text": "用户划选的转写片段", "record_ids": [record["record_id"]]},
        headers=headers,
    )
    assert response.status_code == 200
    assert "用户划选的转写片段" in captured["user"]
    assert "讨论记录正文" not in captured["user"]
    assert response.json()["data"]["source_record_ids"] == []


def test_organize_falls_back_to_recent_records(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, str] = {}

    def fake_llm(messages, config=None):
        captured["user"] = messages[-1]["content"]
        return "基于最近记录的整理"

    monkeypatch.setattr(ai_chat_service, "_run_organize_llm", fake_llm)
    headers = _auth(client)
    meeting = _meeting(client, headers)
    first = _record(client, headers, meeting["meeting_id"])
    second = _record(client, headers, meeting["meeting_id"])

    response = client.post(
        f"/api/v1/meetings/{meeting['meeting_id']}/organize",
        json={"task": "organize"},
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert "讨论记录正文" in captured["user"]
    assert set(data["source_record_ids"]) == {first["record_id"], second["record_id"]}


def test_organize_audio_id_uses_transcript(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, db_session
) -> None:
    import uuid

    from app.models.audio import MeetingAudio

    captured: dict[str, str] = {}

    def fake_llm(messages, config=None):
        captured["user"] = messages[-1]["content"]
        return "基于转写的整理"

    monkeypatch.setattr(ai_chat_service, "_run_organize_llm", fake_llm)
    headers = _auth(client)
    user_id = client.get(
        "/api/v1/auth/me", headers=headers
    ).json()["data"]["user_id"]
    meeting = _meeting(client, headers)
    audio = MeetingAudio(
        audio_id=f"aud_{uuid.uuid4().hex[:12]}",
        meeting_id=meeting["meeting_id"],
        user_id=user_id,
        file_name="live.webm",
        type="webm",
        storage_key="audio/x/live.webm",
        status="transcribed",
        transcript="这是音频转写全文",
    )
    db_session.add(audio)
    db_session.commit()

    response = client.post(
        f"/api/v1/meetings/{meeting['meeting_id']}/organize",
        json={"audio_id": audio.audio_id},
        headers=headers,
    )
    assert response.status_code == 200
    assert "这是音频转写全文" in captured["user"]
    assert response.json()["data"]["source_record_ids"] == []


def test_organize_audio_without_transcript_rejected(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, db_session
) -> None:
    import uuid

    from app.models.audio import MeetingAudio

    def fail(messages, config=None):
        raise AssertionError("不应调用 LLM")

    monkeypatch.setattr(ai_chat_service, "_run_organize_llm", fail)
    headers = _auth(client)
    user_id = client.get(
        "/api/v1/auth/me", headers=headers
    ).json()["data"]["user_id"]
    meeting = _meeting(client, headers)
    audio = MeetingAudio(
        audio_id=f"aud_{uuid.uuid4().hex[:12]}",
        meeting_id=meeting["meeting_id"],
        user_id=user_id,
        file_name="live.webm",
        type="webm",
        storage_key="audio/x/live.webm",
        status="processing",
        transcript=None,
    )
    db_session.add(audio)
    db_session.commit()

    response = client.post(
        f"/api/v1/meetings/{meeting['meeting_id']}/organize",
        json={"audio_id": audio.audio_id},
        headers=headers,
    )
    assert response.status_code == 422
    assert "尚未成功转写" in response.json()["message"]


def test_organize_model_override_passed(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, object] = {}

    def fake_resolve(db, user_id, *, purpose, model_override=None):
        captured["purpose"] = purpose
        captured["model_override"] = model_override
        return object()

    monkeypatch.setattr(ai_chat_service, "resolve_model_config", fake_resolve)
    monkeypatch.setattr(
        ai_chat_service, "_run_organize_llm", lambda messages, config=None: "整理"
    )
    headers = _auth(client)
    meeting = _meeting(client, headers)
    _record(client, headers, meeting["meeting_id"])

    response = client.post(
        f"/api/v1/meetings/{meeting['meeting_id']}/organize",
        json={"task": "brief", "model": "gpt-4o"},
        headers=headers,
    )
    assert response.status_code == 200
    assert captured["model_override"] == "gpt-4o"


def test_organize_instruction_injected(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, str] = {}

    def fake_llm(messages, config=None):
        captured["user"] = messages[-1]["content"]
        captured["system"] = messages[0]["content"]
        return "整理结果"

    monkeypatch.setattr(ai_chat_service, "_run_organize_llm", fake_llm)
    headers = _auth(client)
    meeting = _meeting(client, headers)
    _record(client, headers, meeting["meeting_id"])

    response = client.post(
        f"/api/v1/meetings/{meeting['meeting_id']}/organize",
        json={"task": "organize", "instruction": "重点关注排期与风险"},
        headers=headers,
    )
    assert response.status_code == 200
    assert "用户补充要求：重点关注排期与风险" in captured["user"]
    assert "用户补充要求" not in captured["system"]


def test_organize_instruction_too_long_rejected(client: TestClient) -> None:
    headers = _auth(client)
    meeting = _meeting(client, headers)
    response = client.post(
        f"/api/v1/meetings/{meeting['meeting_id']}/organize",
        json={"instruction": "长" * 2001},
        headers=headers,
    )
    assert response.status_code == 422


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
