"""Agent API：会话持久化、单轮、确认门与权限隔离。"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.ai.chat import ChatAnswer
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.repositories import agent_repository

REGISTER = "/api/v1/auth/register"
ME = "/api/v1/auth/me"
AGENT = "/api/v1/agent"
MEETINGS = "/api/v1/meetings"
PASSWORD = "secret123"


def _auth(client: TestClient, name: str = "alice") -> dict[str, str]:
    response = client.post(REGISTER, json={"name": name, "password": PASSWORD})
    assert response.status_code == 201, response.text
    token = response.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _user_id(client: TestClient, headers: dict[str, str]) -> str:
    return client.get(ME, headers=headers).json()["data"]["user_id"]


def test_turn_persists_messages_and_reuses_session(client: TestClient) -> None:
    headers = _auth(client)

    first = client.post(
        f"{AGENT}/turns",
        json={"scene": "minutes", "message": "你能做什么", "intent": "help"},
        headers=headers,
    )
    assert first.status_code == 200, first.text
    data = first.json()["data"]
    session_id = data["session_id"]
    assert data["intent"]["intent"] == "help"
    assert data["intent"]["source"] == "explicit"
    assert data["assistant_message"]["role"] == "assistant"

    messages = client.get(
        f"{AGENT}/sessions/{session_id}/messages", headers=headers
    ).json()["data"]
    assert messages["pagination"]["total"] == 2
    assert [item["role"] for item in messages["items"]] == ["user", "assistant"]

    # 不传 session_id：按 user + scene + meeting 复用默认会话
    second = client.post(
        f"{AGENT}/turns",
        json={"scene": "minutes", "message": "再说明一下", "intent": "help"},
        headers=headers,
    )
    assert second.status_code == 200
    assert second.json()["data"]["session_id"] == session_id


def test_session_ownership_isolation(client: TestClient) -> None:
    alice = _auth(client, "alice")
    bob = _auth(client, "bob")

    created = client.post(
        f"{AGENT}/sessions", json={"scene": "minutes"}, headers=alice
    )
    assert created.status_code == 200
    session_id = created.json()["data"]["session_id"]

    assert (
        client.get(f"{AGENT}/sessions/{session_id}", headers=bob).status_code == 404
    )
    assert (
        client.get(
            f"{AGENT}/sessions/{session_id}/messages", headers=bob
        ).status_code
        == 404
    )


def test_session_delete_cascades(client: TestClient) -> None:
    headers = _auth(client)
    session_id = client.post(
        f"{AGENT}/turns",
        json={"scene": "minutes", "message": "你能做什么", "intent": "help"},
        headers=headers,
    ).json()["data"]["session_id"]

    deleted = client.delete(f"{AGENT}/sessions/{session_id}", headers=headers)
    assert deleted.status_code == 200
    assert deleted.json()["data"]["deleted"] is True
    assert (
        client.get(f"{AGENT}/sessions/{session_id}", headers=headers).status_code
        == 404
    )


def test_reject_pending_action(client: TestClient, db_session: Session) -> None:
    headers = _auth(client)
    user_id = _user_id(client, headers)
    session_id = client.post(
        f"{AGENT}/sessions", json={"scene": "minutes"}, headers=headers
    ).json()["data"]["session_id"]

    action = agent_repository.create_pending_action(
        db_session,
        action_id="aga_test_reject",
        session_id=session_id,
        run_id=None,
        user_id=user_id,
        action_type="web_search",
        question="是否联网？",
        payload={"question": "外部信息"},
        expires_at=None,
    )

    pending = client.get(
        f"{AGENT}/sessions/{session_id}/pending-actions", headers=headers
    ).json()["data"]
    assert [item["action_id"] for item in pending] == [action.action_id]

    rejected = client.post(
        f"{AGENT}/pending-actions/{action.action_id}/reject",
        json={},
        headers=headers,
    )
    assert rejected.status_code == 200, rejected.text
    body = rejected.json()["data"]
    assert "已取消" in body["assistant_message"]["content"]
    # 重复处理：幂等冲突
    again = client.post(
        f"{AGENT}/pending-actions/{action.action_id}/reject",
        json={},
        headers=headers,
    )
    assert again.status_code == 409


def test_approve_pending_web_search_without_web(
    client: TestClient, db_session: Session
) -> None:
    """批准联网后，WEB_SEARCH_ENABLED=false 时工作流降级为拒答，不裸报错。"""
    headers = _auth(client)
    user_id = _user_id(client, headers)
    session_id = client.post(
        f"{AGENT}/sessions", json={"scene": "minutes"}, headers=headers
    ).json()["data"]["session_id"]
    action = agent_repository.create_pending_action(
        db_session,
        action_id="aga_test_approve",
        session_id=session_id,
        run_id=None,
        user_id=user_id,
        action_type="web_search",
        question="是否联网？",
        payload={"question": "外部信息"},
        expires_at=None,
    )

    approved = client.post(
        f"{AGENT}/pending-actions/{action.action_id}/approve",
        json={},
        headers=headers,
    )
    assert approved.status_code == 200, approved.text
    body = approved.json()["data"]
    assert body["run"]["workflow"] == "web_fallback"
    assert "无法确认" in body["assistant_message"]["content"]


def test_brief_without_materials_returns_hint(client: TestClient) -> None:
    """会前速览只读本场资料：无资料时明确提示，不调用模型、不产文件。"""
    headers = _auth(client)
    meeting = client.post(
        "/api/v1/meetings", json={"title": "周会"}, headers=headers
    ).json()["data"]

    response = client.post(
        f"{AGENT}/turns",
        json={
            "scene": "preprocess",
            "meeting_id": meeting["meeting_id"],
            "message": "会前速览",
            "intent": "brief",
        },
        headers=headers,
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["intent"]["intent"] == "brief"
    assert "还没有可用资料" in data["assistant_message"]["content"]
    assert data["assistant_message"]["file"] is None


def test_quick_task_requires_text(client: TestClient) -> None:
    headers = _auth(client)
    response = client.post(
        f"{AGENT}/turns",
        json={"scene": "asr", "message": "", "options": {"quick_task": "polish"}},
        headers=headers,
    )
    assert response.status_code == 422
    assert response.json()["error_code"] == "VALIDATION_ERROR"


def test_stream_prep_error_returns_json_error_body(client: TestClient) -> None:
    """首帧前的错误（会话不存在）必须是统一 JSON 错误体，而不是空的 SSE 流。"""
    headers = _auth(client)
    response = client.post(
        f"{AGENT}/turns/stream",
        json={
            "scene": "preprocess",
            "message": "你好",
            "session_id": "ags_not_exist",
            "options": {},
        },
        headers=headers,
    )
    assert response.status_code == 404, response.text
    assert response.json()["error_code"] == "RESOURCE_NOT_FOUND"
    assert response.text.startswith("{")


def test_stream_dispatch_error_returns_error_event(client: TestClient) -> None:
    """事件流开始后的错误以 `error` 事件返回，连接不被截断（前端据此展示原因）。"""
    headers = _auth(client)
    response = client.post(
        f"{AGENT}/turns/stream",
        json={
            "scene": "preprocess",
            "message": "生成会前准备清单",
            "intent": "prepare",
            "options": {},
        },
        headers=headers,
    )
    assert response.status_code == 200, response.text
    body = response.text
    assert "event: intent" in body
    assert "event: error" in body
    assert "VALIDATION_ERROR" in body
    assert "event: done" not in body


def test_agent_disabled_returns_404(
    client: TestClient, monkeypatch
) -> None:
    from app.core.config import get_settings

    monkeypatch.setenv("AGENT_ENABLED", "false")
    get_settings.cache_clear()
    try:
        headers = _auth(client)
        response = client.post(
            f"{AGENT}/turns",
            json={"scene": "minutes", "message": "你能做什么", "intent": "help"},
            headers=headers,
        )
        assert response.status_code == 404
    finally:
        monkeypatch.delenv("AGENT_ENABLED", raising=False)
        get_settings.cache_clear()


# ============================ 思考过程（推理链） ============================


def _sse_events(body: str) -> list[tuple[str, dict]]:
    """解析 SSE 文本为 (event, data) 列表；忽略 `: ping` 心跳注释。"""
    out: list[tuple[str, dict]] = []
    current = ""
    for line in body.splitlines():
        if line.startswith("event: "):
            current = line[len("event: ") :]
        elif line.startswith("data: "):
            out.append((current, json.loads(line[len("data: ") :])))
    return out


def _install_fake_chat_stream(
    monkeypatch, *, thinking_seen: dict | None = None
) -> None:
    """把 `ai_chat_service.prepare_chat` 换成返回 reasoning 流的假实现。"""
    from types import SimpleNamespace

    from app.ai.chat.service import ChatPreparation, Source
    from app.ai.llm import LLMDelta
    from app.services import ai_chat_service

    class _Service:
        model = "fake-model"
        llm = SimpleNamespace(api_base="https://llm.test/v1", model="fake-model")

        async def answer_stream(self, prepared, *, allow_web=True, thinking=True):
            if thinking_seen is not None:
                thinking_seen["thinking"] = thinking
            yield LLMDelta("先看材料里的项目排期。", "reasoning")
            yield LLMDelta("结论是", "content")
            yield LLMDelta("本周五交付。", "content")

    class _Session:
        model = "fake-model"
        service = _Service()
        prepared = ChatPreparation(
            question="结论是什么",
            memory_context="",
            contexts=["原文片段"],
            sources=[
                Source(
                    meeting_id="mtg_x",
                    material_id="mat_x",
                    record_id=None,
                    excerpt="原文片段",
                )
            ],
            has_evidence=True,
        )

    monkeypatch.setattr(ai_chat_service, "prepare_chat", lambda *a, **k: _Session())


def test_chat_stream_emits_reasoning_and_trace(
    client: TestClient, monkeypatch
) -> None:
    """问答流：meta.trace 展示真实步骤，reasoning 透传模型原生推理。"""
    _install_fake_chat_stream(monkeypatch)
    headers = _auth(client)
    meeting = client.post(
        MEETINGS, json={"title": "周会"}, headers=headers
    ).json()["data"]

    response = client.post(
        f"{AGENT}/turns/stream",
        json={
            "scene": "minutes",
            "message": "结论是什么",
            "meeting_id": meeting["meeting_id"],
            "intent": "chat",
            "options": {},
        },
        headers=headers,
    )

    assert response.status_code == 200, response.text
    events = _sse_events(response.text)
    kinds = [kind for kind, _ in events]
    assert kinds == ["intent", "meta", "reasoning", "delta", "delta", "done"]

    def first(kind: str) -> dict:
        return next(data for name, data in events if name == kind)

    trace = first("meta")["trace"]
    assert [stage["id"] for stage in trace["stages"]] == [
        "intent",
        "retrieve",
        "generate",
    ]
    assert trace["stages"][1]["detail"] == "命中 1 条相关片段"
    assert trace["native_reasoning"] is False
    assert first("reasoning")["text"] == "先看材料里的项目排期。"

    done = first("done")
    assert done["reply"]["content"] == "结论是本周五交付。"
    assert done["reply"]["reasoning"] == "先看材料里的项目排期。"

    # 原生推理与执行步骤随消息持久化，历史恢复后可折叠回看
    messages = client.get(
        f"{AGENT}/sessions/{done['session_id']}/messages", headers=headers
    ).json()["data"]
    assistant = [item for item in messages["items"] if item["role"] == "assistant"][-1]
    assert assistant["meta"]["reasoning"] == "先看材料里的项目排期。"
    assert [stage["id"] for stage in assistant["meta"]["trace"]] == [
        "intent",
        "retrieve",
        "generate",
    ]


def test_chat_stream_thinking_off_skips_native_reasoning(
    client: TestClient, monkeypatch
) -> None:
    """关闭思考开关：不请求思考模式，trace 标记为无原生推理。"""
    seen: dict = {}
    _install_fake_chat_stream(monkeypatch, thinking_seen=seen)
    headers = _auth(client)
    meeting = client.post(
        MEETINGS, json={"title": "周会"}, headers=headers
    ).json()["data"]

    response = client.post(
        f"{AGENT}/turns/stream",
        json={
            "scene": "minutes",
            "message": "结论是什么",
            "meeting_id": meeting["meeting_id"],
            "intent": "chat",
            "options": {"thinking": False},
        },
        headers=headers,
    )

    assert response.status_code == 200, response.text
    events = _sse_events(response.text)
    assert seen["thinking"] is False
    meta = next(data for name, data in events if name == "meta")
    assert meta["trace"]["native_reasoning"] is False
    done = next(data for name, data in events if name == "done")
    assert done["reply"]["reasoning"] == "先看材料里的项目排期。"


# ============================ 多轮历史 ============================


class _RecordingChatService:
    """替身：记录问答链路收到的 records / history，并按是否有证据返回。"""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def answer(
        self,
        question,
        *,
        user_id,
        scope,
        current_meeting_id,
        records=None,
        history=None,
        memory_context="",
        mode="plan",
        allow_web=True,
        **kwargs,
    ):
        kept = list(records or [])
        self.calls.append(
            {"question": question, "records": kept, "history": list(history or [])}
        )
        return ChatAnswer(
            answer=f"回答：{question}",
            sources=[],
            insufficient_evidence=not kept,
        )


def _install_recording_chat(monkeypatch) -> _RecordingChatService:
    from app.services import ai_chat_service

    fake = _RecordingChatService()
    monkeypatch.setattr(
        ai_chat_service, "_chat_service", lambda db, user_id, model=None: fake
    )
    return fake


def test_chat_turn_injects_previous_turns(client: TestClient, monkeypatch) -> None:
    """第二轮问答必须带上第一轮的 user/assistant，否则追问无法理解指代。"""
    fake = _install_recording_chat(monkeypatch)
    headers = _auth(client)
    meeting = client.post(MEETINGS, json={"title": "周会"}, headers=headers).json()["data"]
    payload = {
        "scene": "minutes",
        "meeting_id": meeting["meeting_id"],
        "intent": "chat",
    }

    first = client.post(
        f"{AGENT}/turns", json={**payload, "message": "结论是什么"}, headers=headers
    )
    assert first.status_code == 200, first.text
    second = client.post(
        f"{AGENT}/turns", json={**payload, "message": "第二条展开"}, headers=headers
    )
    assert second.status_code == 200, second.text

    assert fake.calls[0]["history"] == []
    assert fake.calls[1]["history"] == [
        {"role": "user", "content": "结论是什么"},
        {"role": "assistant", "content": "回答：结论是什么"},
    ]


# ============================ 证据门 ============================


def test_web_confirmation_only_when_records_unrelated(
    client: TestClient, monkeypatch, db_session: Session
) -> None:
    """记录与问题无关时才算「无证据」；相关时直接作答，不弹联网确认。"""
    monkeypatch.setenv("WEB_SEARCH_ENABLED", "true")
    monkeypatch.setenv("WEB_SEARCH_REQUIRE_CONFIRMATION", "true")
    get_settings.cache_clear()
    try:
        fake = _install_recording_chat(monkeypatch)
        headers = _auth(client)
        meeting = client.post(MEETINGS, json={"title": "周会"}, headers=headers).json()["data"]
        created = client.post(
            f"{MEETINGS}/{meeting['meeting_id']}/records",
            json={"content": "项目排期：周三完成设计稿，周五联调，下周三上线。"},
            headers=headers,
        )
        assert created.status_code == 201, created.text

        payload = {
            "scene": "minutes",
            "meeting_id": meeting["meeting_id"],
            "intent": "chat",
        }

        unrelated = client.post(
            f"{AGENT}/turns",
            json={**payload, "message": "公司的年度市场预算是多少"},
            headers=headers,
        )
        assert unrelated.status_code == 200, unrelated.text
        body = unrelated.json()["data"]
        assert fake.calls[0]["records"] == []
        assert body["pending_action"] is not None
        # 同步路径落库的提示消息也带关联 id，前端刷新后不会补出第二张卡
        assert (
            body["assistant_message"]["meta"]["pending_action_id"]
            == body["pending_action"]["action_id"]
        )
        # 确认门提示本身不进对话历史
        from app.services import ai_chat_service

        history = ai_chat_service.load_history(
            db_session, body["session_id"]
        )
        assert all("联网" not in item["content"] for item in history)

        related = client.post(
            f"{AGENT}/turns",
            json={**payload, "message": "项目排期是什么时候"},
            headers=headers,
        )
        assert related.status_code == 200, related.text
        assert related.json()["data"]["pending_action"] is None
        assert len(fake.calls[1]["records"]) == 1
        assert related.json()["data"]["assistant_message"]["content"] == "回答：项目排期是什么时候"
    finally:
        monkeypatch.delenv("WEB_SEARCH_ENABLED", raising=False)
        monkeypatch.delenv("WEB_SEARCH_REQUIRE_CONFIRMATION", raising=False)
        get_settings.cache_clear()


# ============================ 确认门：幂等与选项 ============================


def test_approve_pending_action_is_idempotent(
    client: TestClient, db_session: Session
) -> None:
    """批准必须原子生效：第二次批准返回 409，副作用不重复执行。"""
    headers = _auth(client)
    user_id = _user_id(client, headers)
    session_id = client.post(
        f"{AGENT}/sessions", json={"scene": "minutes"}, headers=headers
    ).json()["data"]["session_id"]
    action = agent_repository.create_pending_action(
        db_session,
        action_id="aga_test_approve_twice",
        session_id=session_id,
        run_id=None,
        user_id=user_id,
        action_type="web_search",
        question="是否联网？",
        payload={"question": "外部信息"},
        expires_at=None,
    )

    first = client.post(
        f"{AGENT}/pending-actions/{action.action_id}/approve",
        json={},
        headers=headers,
    )
    assert first.status_code == 200, first.text
    second = client.post(
        f"{AGENT}/pending-actions/{action.action_id}/approve",
        json={},
        headers=headers,
    )
    assert second.status_code == 409

    # 副作用只发生一次：批准没有产生第二个工作流实例
    from sqlalchemy import select

    from app.models.agent import AgentRun

    runs = list(
        db_session.execute(
            select(AgentRun).where(AgentRun.session_id == session_id)
        ).scalars()
    )
    assert len(runs) == 1


def test_approve_pending_action_keeps_options(
    client: TestClient, db_session: Session
) -> None:
    """批准后恢复执行必须沿用发起时的模型/思考开关，不能退回默认。"""
    headers = _auth(client)
    user_id = _user_id(client, headers)
    session_id = client.post(
        f"{AGENT}/sessions", json={"scene": "minutes"}, headers=headers
    ).json()["data"]["session_id"]
    action = agent_repository.create_pending_action(
        db_session,
        action_id="aga_test_approve_options",
        session_id=session_id,
        run_id=None,
        user_id=user_id,
        action_type="web_search",
        question="是否联网？",
        payload={
            "question": "外部信息",
            "options": {"model": "gpt-x", "thinking": False},
        },
        expires_at=None,
    )

    approved = client.post(
        f"{AGENT}/pending-actions/{action.action_id}/approve",
        json={},
        headers=headers,
    )
    assert approved.status_code == 200, approved.text
    state = approved.json()["data"]["run"]["state"]
    assert state["options"]["model"] == "gpt-x"
    assert state["options"]["thinking"] is False


# ============================ 失败：run 是唯一事实来源 ============================


def test_workflow_failure_leaves_run_without_failed_message(
    client: TestClient, db_session: Session
) -> None:
    """失败只写 run：不再落 failed 消息，避免与 502 / error 事件重复提示。"""
    from app.agent.service import _persist_run_outcome, _raise_if_run_failed
    from app.agent.workflow import WorkflowResult

    headers = _auth(client)
    user_id = _user_id(client, headers)
    session_id = client.post(
        f"{AGENT}/sessions", json={"scene": "minutes"}, headers=headers
    ).json()["data"]["session_id"]
    run = agent_repository.create_run(
        db_session,
        run_id="agr_test_failed",
        session_id=session_id,
        user_id=user_id,
        meeting_id=None,
        workflow="web_fallback",
        state={"question": "外部信息"},
    )
    result = WorkflowResult(
        status="failed",
        state={"question": "外部信息"},
        current_step="web_search",
        error_code="MODEL_TIMEOUT",
        error_message="模型超时",
    )

    assert _persist_run_outcome(db_session, run=run, result=result, context=None) is None

    messages = agent_repository.list_messages(
        db_session, session_id=session_id, limit=50, offset=0
    )
    assert [message.status for message in messages] == []
    assert run.status == "failed"
    assert run.error_code == "MODEL_TIMEOUT"

    with pytest.raises(AppError) as excinfo:
        _raise_if_run_failed(run)
    assert excinfo.value.http_status == 502
    assert excinfo.value.error_code == "MODEL_TIMEOUT"
