"""AI 调用审计服务（`ai-design.md 3.11`）：预创建运行态 + 终态更新。

把一次 LLM 调用的元数据（场景/模型/用量/耗时/成败/任务关联）落进 `ai_call_logs`：

- **预创建**：`begin_call` 建上下文 → `persist_start` 落一行 `status=running`
  并提交 → 收尾时 `finish_call` 更新为 `success`/`failed`/`cancelled` 并写
  `finished_at`。进程崩溃留下的 `running` 行由僵尸回收兜底（`reap_stale_running`）；
- **同步路径**：服务层用 `with audit_call(db, user_id=..., scene=...)` 包裹
  **纯 LLM 调用段**（此时会话内无未提交业务写入，提交审计行不连带提交业务状态）；
- **流式路径（SSE）**：端点在返回流之前 `begin_call`（同一上下文，保证 usage
  可记入）+ `persist_start`，生成器 `finally` 里 `close_context` 后经
  `finish_in_fresh_session` 收尾（请求 Session 生命周期不确定，且不得阻塞事件循环）；
- **任务关联**：`task_runner.run_job` 经 `audit.bind_job` 绑定 job_id，
  `begin_call` 自动读取并写入 `job_id`；
- **LLMClient** 经 `app/ai/audit.py` 的上下文把实际模型与 usage 记入同一事件
  （含结构化修复重试与降级切换的累计）；
- **审计是旁路**：任何落库失败只记 warning 并回滚，绝不影响业务调用；
  业务异常原样上抛。

日志红线：只写数值与枚举标签，不写提示词、用户原文或模型输出。
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import Token
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.ai import audit
from app.ai.chain import parse_fallback_models
from app.ai.pricing import estimate_cost_usd
from app.ai.scenes import get_scene
from app.core import metrics
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.db.session import SessionLocal
from app.models.ai_call_log import AICallLog
from app.repositories import ai_call_log_repository
from app.utils.ids import new_id

logger = logging.getLogger(__name__)

# SSE 收尾用的独立短会话工厂（与 task_runner.session_factory 同模式，测试可替换）
session_factory: Callable[[], Session] = SessionLocal

# 终态取值
STATUS_RUNNING = "running"
STATUS_SUCCESS = "success"
STATUS_FAILED = "failed"
STATUS_CANCELLED = "cancelled"

# 流式消费端提前关闭（前端断开）
ERROR_CLIENT_DISCONNECTED = "CLIENT_DISCONNECTED"
# 僵尸回收：进程崩溃/未收尾的 running 行
ERROR_INTERRUPTED = "AI_CALL_INTERRUPTED"


@dataclass
class AuditHandle:
    """一次被审计调用的句柄：审计上下文 +（可能尚未写入的）审计行。"""

    log_id: str | None
    user_id: str
    event: audit.AuditEvent
    purpose: str | None
    token: Token
    started: float
    context_closed: bool = False
    finished: bool = False


def begin_call(
    *,
    user_id: str,
    scene: str,
    model: str = "",
    provider: str = "",
    transport: str = "sync",
) -> AuditHandle:
    """建立审计上下文并返回句柄（**不写库**）。

    必须在后续消费 LLM 增量/记录 usage 的同一上下文中调用（SSE 端点在
    事件循环线程调用，保证 `stream.__anext__()` 能记入事件）。
    """
    spec = get_scene(scene)
    event = audit.AuditEvent(
        scene=scene,
        model=model,
        provider=provider,
        transport=transport,
        job_id=audit.current_job_id(),
        # 降级来源：本期只有全局 env 链；user/scene/cross_provider 为后续演进
        fallback_scope=(
            "global" if parse_fallback_models(get_settings().llm_fallback_models) else "none"
        ),
    )
    token = audit.begin(event)
    return AuditHandle(
        log_id=None,
        user_id=user_id,
        event=event,
        purpose=spec.purpose.value if spec.purpose else None,
        token=token,
        started=time.monotonic(),
    )


def persist_start(db: Session, handle: AuditHandle) -> None:
    """预创建 `running` 审计行并提交；失败只告警（审计旁路）。"""
    if handle.log_id is not None:
        return
    event = handle.event
    try:
        log = AICallLog(
            log_id=new_id("ail"),
            user_id=handle.user_id,
            scene=event.scene,
            purpose=handle.purpose,
            model=event.model or "-",
            provider=event.provider or "-",
            transport=event.transport,
            status=STATUS_RUNNING,
            job_id=event.job_id,
            fallback_scope=event.fallback_scope,
            meta=dict(event.meta),
        )
        ai_call_log_repository.insert(db, log)
        handle.log_id = log.log_id
    except Exception:  # noqa: BLE001 — 审计旁路：失败不影响业务
        logger.warning("AI 审计预创建失败 scene=%s", event.scene, exc_info=True)
        try:
            db.rollback()
        except Exception:  # noqa: BLE001
            logger.warning("AI 审计回滚失败", exc_info=True)


def close_context(handle: AuditHandle) -> None:
    """结束审计上下文（幂等；必须在 `begin_call` 的同一上下文/线程调用）。"""
    if handle.context_closed:
        return
    handle.context_closed = True
    audit.end(handle.token)


def _record_metrics(handle: AuditHandle) -> None:
    """指标与落库解耦：即使 DB 失败也要计数。"""
    event = handle.event
    metrics.inc_counter("ai_call_total")
    metrics.inc_counter(f"ai_call_total/{event.scene}")
    if event.status == STATUS_FAILED:
        metrics.inc_counter("ai_call_error_total")
        metrics.inc_counter(f"ai_call_error_total/{event.scene}")
    metrics.observe("ai_call_latency_ms", event.latency_ms)


def finish_call(
    db: Session | None,
    handle: AuditHandle,
    *,
    status: str | None = None,
    error_code: str | None = None,
) -> None:
    """写终态 + 指标（幂等）；DB 失败只告警，不影响业务。

    `db=None` 时只算指标不写库（会话工厂不可用的兜底）。**不结束上下文**——
    上下文必须由调用方在 `begin_call` 的同一线程经 `close_context` 结束。
    """
    if handle.finished:
        return
    handle.finished = True
    event = handle.event
    if status is not None:
        event.status = status
    if error_code is not None:
        event.error_code = error_code
    event.latency_ms = int((time.monotonic() - handle.started) * 1000)
    event.finished = True

    if db is not None and handle.log_id is not None:
        try:
            ai_call_log_repository.finish(
                db,
                handle.log_id,
                status=event.status,
                error_code=event.error_code,
                model=event.model or "-",
                provider=event.provider or "-",
                input_tokens=event.input_tokens or None,
                output_tokens=event.output_tokens or None,
                cost_usd=estimate_cost_usd(
                    event.model, event.input_tokens, event.output_tokens
                ),
                latency_ms=event.latency_ms,
                fallback_from=event.fallback_from,
                fallback_scope=event.fallback_scope,
                meta=dict(event.meta),
                finished_at=datetime.now(UTC),
            )
        except Exception:  # noqa: BLE001 — 审计旁路：失败不影响业务
            logger.warning(
                "AI 审计终态写入失败 scene=%s", event.scene, exc_info=True
            )
            try:
                db.rollback()
            except Exception:  # noqa: BLE001
                logger.warning("AI 审计回滚失败", exc_info=True)

    _record_metrics(handle)


def finish_in_fresh_session(
    handle: AuditHandle, *, status: str, error_code: str | None = None
) -> None:
    """SSE 收尾：用独立短会话写终态（阻塞部分须放线程池执行）。

    请求 Session 的生命周期不确定，且事件循环线程不得做同步 DB 访问。
    """
    db: Session | None = None
    try:
        db = session_factory()
    except Exception:  # noqa: BLE001
        logger.warning("AI 审计会话创建失败", exc_info=True)
    try:
        finish_call(db, handle, status=status, error_code=error_code)
    finally:
        if db is not None:
            db.close()


@contextmanager
def audit_call(
    db: Session,
    *,
    user_id: str,
    scene: str,
    model: str = "",
    provider: str = "",
    transport: str = "sync",
) -> Iterator[audit.AuditEvent]:
    """包裹一次同步 LLM 调用：预创建 `running` 行，退出时写终态。

    - `model`/`provider` 为配置值兜底，LLMClient 的实际调用会覆盖事件字段；
    - `AppError` 与未知异常都记为 `failed` 后原样上抛；
    - `GeneratorExit`（生成器被消费端提前关闭）不记为失败，按现状落库。
    """
    handle = begin_call(
        user_id=user_id,
        scene=scene,
        model=model,
        provider=provider,
        transport=transport,
    )
    persist_start(db, handle)
    try:
        yield handle.event
    except AppError as exc:
        handle.event.status = STATUS_FAILED
        handle.event.error_code = exc.error_code
        raise
    except GeneratorExit:
        # 不是 provider 失败：按现状落库
        raise
    except Exception as exc:  # noqa: BLE001 — 记录后原样上抛
        handle.event.status = STATUS_FAILED
        handle.event.error_code = "INTERNAL_ERROR"
        logger.warning(
            "AI 调用异常 scene=%s type=%s", scene, type(exc).__name__
        )
        raise
    finally:
        close_context(handle)
        finish_call(db, handle)


def reap_stale_running(db: Session, *, older_than_minutes: int | None = None) -> int:
    """回收僵尸审计行：超窗未收尾的 `running` → `failed AI_CALL_INTERRUPTED`。"""
    minutes = (
        get_settings().ai_audit_stale_minutes
        if older_than_minutes is None
        else older_than_minutes
    )
    if minutes <= 0:
        return 0
    now = datetime.now(UTC)
    return ai_call_log_repository.reap_running(
        db, cutoff=now - timedelta(minutes=minutes), finished_at=now
    )


def reap_stale_on_startup() -> None:
    """启动时兜底回收上次进程残留的 `running` 行；失败只告警、不阻断启动。"""
    db = session_factory()
    try:
        count = reap_stale_running(db)
        if count:
            logger.warning("启动回收超时审计行 count=%s", count)
    except Exception:  # noqa: BLE001 — 启动探活失败不应阻止服务启动
        logger.exception("启动回收超时审计行失败（忽略，读取时仍会懒回收）")
    finally:
        db.close()


def event_snapshot(event: audit.AuditEvent | None) -> dict[str, Any]:
    """把审计事件转成可序列化快照（供测试与排障，不含用户内容）。"""
    if event is None:
        return {}
    return {
        "scene": event.scene,
        "model": event.model,
        "status": event.status,
        "error_code": event.error_code,
        "input_tokens": event.input_tokens,
        "output_tokens": event.output_tokens,
        "fallback_from": event.fallback_from,
        "fallback_scope": event.fallback_scope,
        "job_id": event.job_id,
        "latency_ms": event.latency_ms,
    }
