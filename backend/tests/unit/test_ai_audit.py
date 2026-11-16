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
    assert event.meta.get("chain_len") == "2"  # 主模型 + 备用模型
    rows = _logs(db_session, user_id)
    assert rows[0].fallback_from == "audit-model"
    assert rows[0].model == "backup-model"
    assert rows[0].fallback_scope == "global"  # 全局 env 降级链
    assert rows[0].meta == {"chain_len": "2"}


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
        "fallback_scope",
        "job_id",
        "latency_ms",
    }
    # 无上下文时为空快照
    assert ai_audit_service.event_snapshot(None) == {}


# ----------------------- 运行态：预创建 + 终态更新 -----------------------


def test_precreate_running_then_finalize_success(db_session: Session) -> None:
    """调用开始先落 running 行，收尾更新为 success 并写 finished_at。"""
    user_id = _user(db_session)

    handle = ai_audit_service.begin_call(
        user_id=user_id, scene="chat", model="m1", provider="p.test"
    )
    ai_audit_service.persist_start(db_session, handle)

    rows = _logs(db_session, user_id)
    assert len(rows) == 1
    assert rows[0].status == "running"  # 运行态可见
    assert rows[0].finished_at is None
    assert rows[0].job_id is None
    assert rows[0].fallback_scope in ("none", "global")

    ai_audit_service.close_context(handle)
    ai_audit_service.finish_call(db_session, handle)

    rows = _logs(db_session, user_id)
    assert rows[0].status == "success"
    assert rows[0].finished_at is not None
    assert rows[0].latency_ms >= 0
    assert rows[0].model == "m1"


def test_finish_call_is_idempotent(db_session: Session) -> None:
    """重复收尾只写一行、只计一次指标。"""
    user_id = _user(db_session)
    handle = ai_audit_service.begin_call(user_id=user_id, scene="chat")
    ai_audit_service.persist_start(db_session, handle)
    ai_audit_service.close_context(handle)

    ai_audit_service.finish_call(db_session, handle)
    ai_audit_service.finish_call(db_session, handle, status="failed")

    rows = _logs(db_session, user_id)
    assert len(rows) == 1
    assert rows[0].status == "success"  # 第二次调用被忽略
    assert metrics.snapshot()["counters"].get("ai_call_total") == 1


def test_finish_call_cancelled_status(db_session: Session) -> None:
    """流式消费端提前关闭 → cancelled + CLIENT_DISCONNECTED。"""
    user_id = _user(db_session)
    handle = ai_audit_service.begin_call(
        user_id=user_id, scene="chat", transport="sse"
    )
    ai_audit_service.persist_start(db_session, handle)
    ai_audit_service.close_context(handle)
    ai_audit_service.finish_call(
        db_session,
        handle,
        status=ai_audit_service.STATUS_CANCELLED,
        error_code=ai_audit_service.ERROR_CLIENT_DISCONNECTED,
    )

    rows = _logs(db_session, user_id)
    assert rows[0].status == "cancelled"
    assert rows[0].error_code == "CLIENT_DISCONNECTED"
    assert rows[0].finished_at is not None


def test_precreate_failure_is_bypassed(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """预创建失败（DB 故障）不阻断调用：无行、指标仍计数。"""
    from app.repositories import ai_call_log_repository

    user_id = _user(db_session)

    def boom(*args, **kwargs):
        raise RuntimeError("db down")

    monkeypatch.setattr(ai_call_log_repository, "insert", boom)

    handle = ai_audit_service.begin_call(user_id=user_id, scene="chat")
    ai_audit_service.persist_start(db_session, handle)
    assert handle.log_id is None  # 行未创建

    ai_audit_service.close_context(handle)
    ai_audit_service.finish_call(db_session, handle)

    assert _logs(db_session, user_id) == []
    assert metrics.snapshot()["counters"].get("ai_call_total") == 1


def test_job_context_linked_into_audit_row(db_session: Session) -> None:
    """task_runner 绑定的 job_id 自动写入审计行（任务↔调用链路）。"""
    from app.ai import audit as audit_context

    user_id = _user(db_session)
    token = audit_context.bind_job("job_abc123")
    try:
        handle = ai_audit_service.begin_call(user_id=user_id, scene="minutes")
        ai_audit_service.persist_start(db_session, handle)
    finally:
        audit_context.unbind_job(token)
    ai_audit_service.close_context(handle)
    ai_audit_service.finish_call(db_session, handle)

    rows = _logs(db_session, user_id)
    assert rows[0].job_id == "job_abc123"
    assert rows[0].scene == "minutes"
    # 解绑后不残留
    assert audit_context.current_job_id() is None


def test_fallback_scope_defaults_to_none(db_session: Session) -> None:
    """未配置降级链 → fallback_scope=none（user/scene/cross_provider 为预留值）。"""
    from app.core.config import get_settings

    user_id = _user(db_session)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(get_settings(), "llm_fallback_models", "")
        handle = ai_audit_service.begin_call(user_id=user_id, scene="chat")
    ai_audit_service.persist_start(db_session, handle)
    ai_audit_service.close_context(handle)
    ai_audit_service.finish_call(db_session, handle)

    assert _logs(db_session, user_id)[0].fallback_scope == "none"


def test_reap_running_marks_interrupted(db_session: Session) -> None:
    """超窗未收尾的 running 行由僵尸回收兜底为 failed AI_CALL_INTERRUPTED。"""
    from datetime import UTC, datetime, timedelta

    user_id = _user(db_session)
    handle = ai_audit_service.begin_call(user_id=user_id, scene="chat")
    ai_audit_service.persist_start(db_session, handle)
    ai_audit_service.close_context(handle)

    # 把受理时间拨到 2 小时前（模拟进程崩溃残留）
    row = _logs(db_session, user_id)[0]
    row.created_at = datetime.now(UTC) - timedelta(hours=2)
    db_session.commit()

    count = ai_audit_service.reap_stale_running(db_session, older_than_minutes=30)
    assert count == 1

    db_session.expire_all()
    rows = _logs(db_session, user_id)
    assert rows[0].status == "failed"
    assert rows[0].error_code == "AI_CALL_INTERRUPTED"
    assert rows[0].finished_at is not None

    # 幂等：再次回收不重复计数
    assert ai_audit_service.reap_stale_running(db_session, older_than_minutes=30) == 0
