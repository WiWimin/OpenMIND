"""B4 AI 调用审计：pricing 估算、audit_call 落库、LLM 用量记入、旁路容错。"""

from __future__ import annotations

from decimal import Decimal

import httpx
import pytest
from sqlalchemy.orm import Session

from app.ai.llm import LLMClient
from app.ai.pricing import estimate_cost_usd, price_for
from app.core import metrics
from app.core.exceptions import AppError
from app.models.ai_call_log import AICallLog
from app.models.user import User
from app.services import ai_audit_service
from app.utils.ids import new_id

API_BASE = "https://audit.test/v1"


def _user(db: Session) -> str:
    user = User(user_id=new_id("usr"), name="audit-user", password_hash="x")
    db.add(user)
    db.commit()
    return user.user_id


def _client(handler) -> LLMClient:
    return LLMClient(
        api_base=API_BASE,
        api_key="sk-test",
        model="audit-model",
        transport=httpx.MockTransport(handler),
    )


def _ok(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "model": "audit-model",
            "choices": [{"message": {"content": "好"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        },
        request=request,
    )


def _logs(db: Session, user_id: str) -> list[AICallLog]:
    from sqlalchemy import select

    rows = db.execute(
        select(AICallLog).where(AICallLog.user_id == user_id)
    ).scalars()
    return list(rows)


# ------------------------------- pricing -------------------------------


def test_price_for_matches_longest_prefix() -> None:
    assert price_for("gpt-4o-mini-2024") is not None
    assert price_for("gpt-4o") is not None
    # gpt-4o 不应抢走 gpt-4o-mini 的单价
    mini = price_for("gpt-4o-mini")
    plain = price_for("gpt-4o")
    assert mini is not None and plain is not None
    assert mini.input_per_m < plain.input_per_m
    assert price_for("unknown-model-xyz") is None
    assert price_for("") is None


def test_estimate_cost_computes_and_quantizes() -> None:
    # gpt-4o-mini: 0.15/0.60 每 M；1_000_000 in + 1_000_000 out = 0.75
    cost = estimate_cost_usd("gpt-4o-mini", 1_000_000, 1_000_000)
    assert cost == Decimal("0.750000")

    assert estimate_cost_usd("unknown-model", 1000, 1000) is None
    assert estimate_cost_usd("gpt-4o-mini", 0, 0) is None
    assert estimate_cost_usd("gpt-4o-mini", None, None) is None


# --------------------------- audit_call 落库 ---------------------------


def test_audit_call_writes_success_row(db_session: Session) -> None:
    user_id = _user(db_session)

    with ai_audit_service.audit_call(
        db_session, user_id=user_id, scene="chat", model="m1", provider="p.test"
    ) as event:
        event.input_tokens = 10
        event.output_tokens = 5

    rows = _logs(db_session, user_id)
    assert len(rows) == 1
    row = rows[0]
    assert row.log_id.startswith("ail_")
    assert row.scene == "chat"
    assert row.purpose == "chat"  # scenes 注册表推导
    assert row.model == "m1"
    assert row.provider == "p.test"
    assert row.status == "success"
    assert row.input_tokens == 10 and row.output_tokens == 5
    assert row.cost_usd is None  # 未知单价
    assert row.latency_ms >= 0


def test_audit_call_writes_failed_row_and_reraises(
    db_session: Session,
) -> None:
    user_id = _user(db_session)

    with pytest.raises(AppError) as exc_info:
        with ai_audit_service.audit_call(
            db_session, user_id=user_id, scene="minutes", model="m1"
        ):
            raise AppError("MODEL_TIMEOUT", "超时", http_status=504, retryable=True)

    assert exc_info.value.error_code == "MODEL_TIMEOUT"
    rows = _logs(db_session, user_id)
    assert len(rows) == 1
    assert rows[0].status == "failed"
    assert rows[0].error_code == "MODEL_TIMEOUT"
    assert rows[0].scene == "minutes"
    assert rows[0].purpose == "minutes"


def test_audit_call_records_unknown_exception(db_session: Session) -> None:
    user_id = _user(db_session)

    with pytest.raises(RuntimeError):
        with ai_audit_service.audit_call(
            db_session, user_id=user_id, scene="prepare"
        ):
            raise RuntimeError("boom")

    rows = _logs(db_session, user_id)
    assert rows[0].status == "failed"
    assert rows[0].error_code == "INTERNAL_ERROR"


def test_audit_metrics_counted(db_session: Session) -> None:
    user_id = _user(db_session)

    with ai_audit_service.audit_call(db_session, user_id=user_id, scene="chat"):
        pass
    with pytest.raises(AppError):
        with ai_audit_service.audit_call(
            db_session, user_id=user_id, scene="chat"
        ):
            raise AppError("MODEL_TIMEOUT", "x", http_status=504)

    counters = metrics.snapshot()["counters"]
    assert counters["ai_call_total"] == 2
    assert counters["ai_call_total/chat"] == 2
    assert counters["ai_call_error_total"] == 1
    assert metrics.snapshot()["windows"]["ai_call_latency_ms"]["samples"] == 2


def test_audit_write_failure_does_not_break_business(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """审计是旁路：落库抛错只告警，业务异常/正常返回不受影响。"""
    from app.repositories import ai_call_log_repository

    user_id = _user(db_session)

    def boom(*args, **kwargs):
        raise RuntimeError("db down")

    monkeypatch.setattr(ai_call_log_repository, "insert", boom)

    # 正常路径不受影响
    with ai_audit_service.audit_call(db_session, user_id=user_id, scene="chat"):
        pass

    # 业务异常原样上抛（不是审计的 RuntimeError）
    with pytest.raises(AppError):
        with ai_audit_service.audit_call(db_session, user_id=user_id, scene="chat"):
            raise AppError("MODEL_TIMEOUT", "x", http_status=504)


# ----------------------- LLMClient 记入审计事件 -----------------------


def test_chat_usage_recorded_into_event(db_session: Session) -> None:
    user_id = _user(db_session)

    with ai_audit_service.audit_call(
        db_session, user_id=user_id, scene="chat", model="cfg-model"
    ) as event:
        _client(_ok).chat([{"role": "user", "content": "x"}], scene="chat")

    assert event.input_tokens == 10
    assert event.output_tokens == 5
    assert event.model == "audit-model"  # 覆盖为实际返回模型
    assert event.provider == "audit.test"
    assert event.status == "success"

    rows = _logs(db_session, user_id)
    assert rows[0].input_tokens == 10
    assert rows[0].model == "audit-model"


def test_scene_mismatch_does_not_leak_usage(db_session: Session) -> None:
    """RAG Judge（scene=rag_judge）在 chat 审计上下文中调用不计入 chat 用量。"""
    user_id = _user(db_session)

    with ai_audit_service.audit_call(
        db_session, user_id=user_id, scene="chat"
    ) as event:
        _client(_ok).chat([{"role": "user", "content": "x"}], scene="rag_judge")

    assert event.input_tokens == 0
    assert event.output_tokens == 0


def test_fallback_start_recorded_in_event(db_session: Session) -> None:
    from app.core.config import get_settings

    user_id = _user(db_session)

    def handler(request: httpx.Request) -> httpx.Response:
        import json as _json

        model = _json.loads(request.content)["model"]
        if model == "audit-model":
            return httpx.Response(402, json={"error": {"code": "insufficient_quota"}})
        return httpx.Response(
            200,
            json={
                "model": model,
                "choices": [{"message": {"content": "好"}}],
                "usage": {"prompt_tokens": 3, "completion_tokens": 2},
            },
            request=request,
        )

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(get_settings(), "llm_fallback_models", "backup-model")
        with ai_audit_service.audit_call(
            db_session, user_id=user_id, scene="chat", model="audit-model"
        ) as event:
            _client(handler).chat([{"role": "user", "content": "x"}], scene="chat")

    assert event.fallback_from == "audit-model"
    assert event.model == "backup-model"  # 实际成功的候选
    rows = _logs(db_session, user_id)
    assert rows[0].fallback_from == "audit-model"
    assert rows[0].model == "backup-model"


def test_event_snapshot_has_no_content(db_session: Session) -> None:
    with ai_audit_service.audit_call(db_session, user_id=_user(db_session), scene="chat") as event:
        snap = ai_audit_service.event_snapshot(event)
    assert set(snap) == {
        "scene",
        "model",
        "status",
        "error_code",
        "input_tokens",
        "output_tokens",
        "fallback_from",
        "latency_ms",
    }
    # 无上下文时为空快照
    assert ai_audit_service.event_snapshot(None) == {}
