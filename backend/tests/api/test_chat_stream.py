"""SSE 流式问答（POST /meetings/{id}/chat/stream）：事件协议、开关与错误策略。

事件顺序 meta → delta → done；首增量前错误回退普通 JSON 错误体，
首增量后错误下发 `event: error`。LLM 与检索用假实现（不发真实请求）。
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.ai import audit as audit_context
from app.ai.chat import ChatService
from app.ai.llm import LLMDelta
from app.core import metrics
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.services import ai_chat_service

REGISTER = "/api/v1/auth/register"
MEETINGS = "/api/v1/meetings"

PASSWORD = "secret123"

_REFUSAL = "根据现有材料无法确认该问题的答案。"


def _auth(client: TestClient, name: str = "alice") -> dict[str, str]:
    response = client.post(REGISTER, json={"name": name, "password": PASSWORD})
    token = response.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _meeting(client: TestClient, headers: dict[str, str]) -> dict:
    response = client.post(MEETINGS, json={"title": "周会"}, headers=headers)
    assert response.status_code == 201
    return response.json()["data"]


def _stream(
    client: TestClient, headers: dict[str, str], meeting_id: str, **payload
):
    body = {"question": "结论是什么？"}
    body.update(payload)
    return client.post(
        f"{MEETINGS}/{meeting_id}/chat/stream", json=body, headers=headers
    )


class FakeLLM:
    """流式 LLM 假实现：按序吐增量，可在第 N 个增量处抛错。

    `deltas` 元素可以是正文字符串，或 `(kind, text)` 元组
    （`kind="reasoning"` 模拟原生推理）。
    """

    def __init__(
        self,
        deltas: tuple[str | tuple[str, str], ...] = ("默认", "答案"),
        *,
        error: AppError | None = None,
        error_at: int | None = None,
        usage: dict[str, int] | None = None,
    ) -> None:
        self.model = "fake-model"
        self.api_base = "https://llm.test/v1"
        self.deltas = list(deltas)
        self.error = error
        self.error_at = 0 if (error is not None and error_at is None) else error_at
        self.usage = usage
        self.thinking_seen: bool | None = None

    async def astream_chat_events(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        timeout_s: float | None = None,
        on_usage=None,
        scene: str | None = None,
        thinking: bool = True,
    ):
        self.thinking_seen = thinking
        for index, item in enumerate(self.deltas):
            if self.error is not None and index >= (self.error_at or 0):
                raise self.error
            if isinstance(item, tuple):
                yield LLMDelta(item[1], item[0])  # type: ignore[arg-type]
            else:
                yield LLMDelta(item, "content")
        if self.error is not None and len(self.deltas) <= (self.error_at or 0):
            raise self.error
        if on_usage and self.usage:
            # 与真实 LLMClient 一致：usage 先记入审计上下文，再回调调用方
            audit_context.note_usage(self.usage, scene=scene)
            on_usage(self.usage)


class FakeRetriever:
    def __init__(self, chunks: list | None = None) -> None:
        self._chunks = chunks or []

    def retrieve(self, query: str, **kwargs):
        return self._chunks


def _install(
    monkeypatch: pytest.MonkeyPatch, llm: FakeLLM, retriever: FakeRetriever | None = None
) -> None:
    service = ChatService(llm, retriever or FakeRetriever())  # type: ignore[arg-type]
    monkeypatch.setattr(
        ai_chat_service, "_chat_service", lambda db, user_id, model=None: service
    )


def _chunk() -> SimpleNamespace:
    return SimpleNamespace(
        meeting_id="mtg_x",
        material_id="mat_x",
        record_id=None,
        excerpt="原文片段",
    )


def _events(body: str) -> list[tuple[str, str]]:
    """解析 SSE 文本为 (event, data) 列表；忽略 `: ping` 心跳注释。"""
    out: list[tuple[str, str]] = []
    current: str | None = None
    for line in body.splitlines():
        if line.startswith("event: "):
            current = line[len("event: ") :]
        elif line.startswith("data: "):
            out.append((current or "", line[len("data: ") :]))
    return out


@contextmanager
def _sse_disabled() -> Iterator[None]:
    os.environ["SSE_CHAT_ENABLED"] = "false"
    get_settings.cache_clear()
    try:
        yield
    finally:
        os.environ.pop("SSE_CHAT_ENABLED", None)
        get_settings.cache_clear()


# ============================ 正常流 ============================


def test_stream_meta_then_deltas_then_done(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install(
        monkeypatch,
        FakeLLM(deltas=("你", "好"), usage={"input": 9, "output": 3}),
        FakeRetriever([_chunk()]),
    )
    headers = _auth(client)
    meeting = _meeting(client, headers)

    response = _stream(client, headers, meeting["meeting_id"])

    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-cache"
    assert response.headers.get("x-accel-buffering") == "no"

    body = response.text
    # 字节顺序：meta 必须先于首个 delta
    assert body.index("event: meta") < body.index("event: delta")
    assert body.index("event: delta") < body.index("event: done")

    events = _events(body)
    assert [kind for kind, _ in events] == ["meta", "delta", "delta", "done"]

    meta = json.loads(events[0][1])
    assert meta["insufficient_evidence"] is False
    assert meta["model"] == "fake-model"
    assert meta["sources"][0]["excerpt"] == "原文片段"
    assert meta["sources"][0]["origin"] == "material"

    assert json.loads(events[1][1])["text"] == "你"
    assert json.loads(events[2][1])["text"] == "好"

    done = json.loads(events[-1][1])
    assert done["answer"] == "你好"
    assert done["usage"] == {"input": 9, "output": 3}
    assert isinstance(done["latency_ms"], int)


def test_stream_include_sources_false(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install(monkeypatch, FakeLLM(), FakeRetriever([_chunk()]))
    headers = _auth(client)
    meeting = _meeting(client, headers)

    response = _stream(
        client, headers, meeting["meeting_id"], include_sources=False
    )

    assert response.status_code == 200
    events = _events(response.text)
    meta = json.loads(events[0][1])
    assert meta["sources"] == []


def test_stream_metrics_recorded(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install(monkeypatch, FakeLLM(deltas=("一段回答",)))
    headers = _auth(client)
    meeting = _meeting(client, headers)

    assert _stream(client, headers, meeting["meeting_id"]).status_code == 200

    snapshot = metrics.snapshot()
    assert snapshot["counters"].get("chat_stream_total") == 1
    assert "chat_stream_first_token_ms" in snapshot["windows"]
    assert snapshot["windows"]["chat_stream_first_token_ms"]["samples"] == 1
    assert snapshot["counters"].get("chat_stream_error_total") in (None, 0)


# ============================ 思考过程（推理链） ============================


def test_stream_emits_reasoning_and_trace(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """reasoning 增量先于正文；done.answer 只含正文，trace 为真实步骤。"""
    _install(
        monkeypatch,
        FakeLLM(deltas=(("reasoning", "先看资料里的排期。"), "结论", "如下")),
        FakeRetriever([_chunk()]),
    )
    headers = _auth(client)
    meeting = _meeting(client, headers)

    response = _stream(client, headers, meeting["meeting_id"])

    assert response.status_code == 200, response.text
    events = _events(response.text)
    assert [kind for kind, _ in events] == [
        "meta",
        "reasoning",
        "delta",
        "delta",
        "done",
    ]

    meta = json.loads(events[0][1])
    trace = meta["trace"]
    assert [stage["id"] for stage in trace["stages"]] == [
        "intent",
        "retrieve",
        "generate",
    ]
    assert trace["stages"][1]["detail"] == "命中 1 条相关片段"
    # fake 模型不具备思考能力 → native_reasoning=false（前端据此提示）
    assert trace["native_reasoning"] is False

    assert json.loads(events[1][1])["text"] == "先看资料里的排期。"

    done = json.loads(events[-1][1])
    assert done["answer"] == "结论如下"
    assert done["reasoning"] == "先看资料里的排期。"
    assert isinstance(done["reasoning_ms"], int)


def test_stream_thinking_off_reaches_llm(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """关闭思考开关：请求级 thinking=false 透传到 LLM。"""
    llm = FakeLLM(deltas=("好",))
    _install(monkeypatch, llm, FakeRetriever([_chunk()]))
    headers = _auth(client)
    meeting = _meeting(client, headers)

    response = _stream(client, headers, meeting["meeting_id"], thinking=False)

    assert response.status_code == 200, response.text
    assert llm.thinking_seen is False


# ============================ 证据不足拒答 ============================


def test_stream_insufficient_evidence_yields_refusal(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    # 无检索命中 + 无会议记录 + 联网无结果 → 单段拒答文案
    monkeypatch.setattr("app.ai.chat.service.web_search", lambda query: [])
    _install(monkeypatch, FakeLLM(), FakeRetriever([]))
    headers = _auth(client)
    meeting = _meeting(client, headers)

    response = _stream(client, headers, meeting["meeting_id"])

    assert response.status_code == 200
    events = _events(response.text)
    assert [kind for kind, _ in events] == ["meta", "delta", "done"]
    assert json.loads(events[0][1])["insufficient_evidence"] is True
    assert json.loads(events[1][1])["text"] == _REFUSAL
    assert json.loads(events[2][1])["answer"] == _REFUSAL


# ============================ 首增量前错误 → JSON ============================


def test_preflight_error_returns_json_error(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    timeout = AppError(
        "MODEL_TIMEOUT", "模型服务超时", http_status=504, retryable=True
    )
    _install(
        monkeypatch,
        FakeLLM(deltas=("不该出现",), error=timeout, error_at=0),
        FakeRetriever([_chunk()]),
    )
    headers = _auth(client)
    meeting = _meeting(client, headers)

    response = _stream(client, headers, meeting["meeting_id"])

    assert response.status_code == 504
    assert response.headers["content-type"].startswith("application/json")
    body = response.json()
    assert body["error_code"] == "MODEL_TIMEOUT"
    assert body["retryable"] is True
    assert "event:" not in response.text  # 尚未进入流

    assert metrics.snapshot()["counters"].get("chat_stream_error_total") == 1
    assert metrics.snapshot()["counters"].get("chat_stream_total") in (None, 0)


# ============================ 首增量后错误 → error 事件 ============================


def test_midstream_error_emits_error_event(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    timeout = AppError(
        "MODEL_TIMEOUT", "模型服务超时", http_status=504, retryable=True
    )
    _install(
        monkeypatch,
        FakeLLM(deltas=("第一段",), error=timeout, error_at=1),
        FakeRetriever([_chunk()]),
    )
    headers = _auth(client)
    meeting = _meeting(client, headers)

    response = _stream(client, headers, meeting["meeting_id"])

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = _events(response.text)
    kinds = [kind for kind, _ in events]
    assert kinds == ["meta", "delta", "error"]
    assert "done" not in kinds  # 失败不下发 done
    error = json.loads(events[-1][1])
    assert error == {
        "status": "error",
        "error_code": "MODEL_TIMEOUT",
        "message": "模型服务超时",
        "retryable": True,
    }

    snapshot = metrics.snapshot()
    assert snapshot["counters"].get("chat_stream_total") == 1
    assert snapshot["counters"].get("chat_stream_error_total") == 1


# ============================ 开关 / 模式 / 权限 ============================


def test_stream_disabled_returns_404(client: TestClient) -> None:
    headers = _auth(client)

    with _sse_disabled():
        response = client.post(
            f"{MEETINGS}/mtg_any/chat/stream",
            json={"question": "?"},
            headers=headers,
        )

    assert response.status_code == 404
    assert response.json()["error_code"] == "RESOURCE_NOT_FOUND"


def test_stream_build_mode_rejected_422(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install(monkeypatch, FakeLLM())
    headers = _auth(client)
    meeting = _meeting(client, headers)

    response = _stream(
        client, headers, meeting["meeting_id"], mode="build"
    )

    assert response.status_code == 422
    assert response.json()["error_code"] == "VALIDATION_ERROR"


def test_stream_requires_auth(client: TestClient) -> None:
    response = client.post(
        f"{MEETINGS}/mtg_x/chat/stream", json={"question": "?"}
    )
    assert response.status_code == 401


def test_stream_meeting_not_found(client: TestClient) -> None:
    response = _stream(client, _auth(client), "mtg_missing")
    assert response.status_code == 404
    assert response.json()["error_code"] == "RESOURCE_NOT_FOUND"


def test_stream_cross_user_forbidden(client: TestClient) -> None:
    alice = _auth(client, "alice")
    meeting = _meeting(client, alice)
    bob = _auth(client, "bob")
    response = _stream(client, bob, meeting["meeting_id"])
    assert response.status_code == 404


# ============================ 审计：SSE 调用落库 ============================


def _audit_rows(db_session) -> list:
    from sqlalchemy import select

    from app.models.ai_call_log import AICallLog

    return list(db_session.execute(select(AICallLog)).scalars())


def test_stream_success_writes_finalized_log(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, db_session
) -> None:
    """成功流：预创建的 running 行被更新为 success（含终态时间与用量）。"""
    _install(
        monkeypatch,
        FakeLLM(deltas=("你", "好"), usage={"input": 9, "output": 3}),
        FakeRetriever([_chunk()]),
    )
    headers = _auth(client)
    meeting = _meeting(client, headers)

    assert _stream(client, headers, meeting["meeting_id"]).status_code == 200

    rows = _audit_rows(db_session)
    assert len(rows) == 1
    row = rows[0]
    assert row.log_id.startswith("ail_")
    assert row.scene == "chat"
    assert row.purpose == "chat"  # scenes 注册表推导
    assert row.transport == "sse"
    assert row.status == "success"
    assert row.error_code is None
    assert row.finished_at is not None  # 运行态已收尾
    assert row.input_tokens == 9 and row.output_tokens == 3
    assert row.job_id is None  # 同步请求无任务关联
    assert row.latency_ms >= 0

    counters = metrics.snapshot()["counters"]
    assert counters.get("ai_call_total") == 1
    assert counters.get("ai_call_error_total") in (None, 0)


def test_stream_preflight_error_writes_failed_log(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, db_session
) -> None:
    """首增量前失败：普通 JSON 错误体之外，审计行必须落 failed。"""
    timeout = AppError("MODEL_TIMEOUT", "模型服务超时", http_status=504, retryable=True)
    _install(
        monkeypatch,
        FakeLLM(deltas=("不该出现",), error=timeout, error_at=0),
        FakeRetriever([_chunk()]),
    )
    headers = _auth(client)
    meeting = _meeting(client, headers)

    response = _stream(client, headers, meeting["meeting_id"])

    assert response.status_code == 504
    rows = _audit_rows(db_session)
    assert len(rows) == 1
    assert rows[0].status == "failed"
    assert rows[0].error_code == "MODEL_TIMEOUT"
    assert rows[0].finished_at is not None


def test_stream_midstream_error_writes_failed_log(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, db_session
) -> None:
    """首增量后失败：`event: error` 之外，审计行必须落 failed。"""
    timeout = AppError("MODEL_TIMEOUT", "模型服务超时", http_status=504, retryable=True)
    _install(
        monkeypatch,
        FakeLLM(deltas=("第一段",), error=timeout, error_at=1),
        FakeRetriever([_chunk()]),
    )
    headers = _auth(client)
    meeting = _meeting(client, headers)

    response = _stream(client, headers, meeting["meeting_id"])

    assert response.status_code == 200
    assert "event: error" in response.text
    rows = _audit_rows(db_session)
    assert len(rows) == 1
    assert rows[0].status == "failed"
    assert rows[0].error_code == "MODEL_TIMEOUT"
    assert rows[0].finished_at is not None
