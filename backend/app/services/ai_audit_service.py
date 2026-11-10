"""AI 调用审计服务（`ai-design.md 3.11`）：`audit_call` 上下文管理器。

把一次 LLM 调用的元数据（场景/模型/用量/耗时/成败）落进 `ai_call_logs`：

- 服务层用 `with audit_call(db, user_id=..., scene=...)` 包裹**纯 LLM 调用段**
  （此时会话内无未提交业务写入，提交审计行不连带提交业务状态）；
- `LLMClient` 经 `app/ai/audit.py` 的上下文把实际模型与 usage 记入同一事件
 （含结构化修复重试与降级切换的累计）；
- **审计是旁路**：落库失败只记 warning 并回滚该会话，绝不影响业务调用；
  业务异常原样上抛。

日志红线：只写数值与枚举标签，不写提示词、用户原文或模型输出。
"""

from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from urllib.parse import urlsplit

from sqlalchemy.orm import Session

from app.ai import audit
from app.ai.pricing import estimate_cost_usd
from app.ai.scenes import get_scene
from app.core import metrics
from app.core.exceptions import AppError
from app.models.ai_call_log import AICallLog
from app.repositories import ai_call_log_repository
from app.utils.ids import new_id

logger = logging.getLogger(__name__)


def _provider_host(api_base: str) -> str:
    return urlsplit(api_base).hostname or "unknown"


def _write(
    db: Session,
    *,
    user_id: str,
    event: audit.AuditEvent,
    purpose: str | None,
) -> None:
    """落库 + 指标；任何失败只告警并回滚，不影响业务。"""
    try:
        log = AICallLog(
            log_id=new_id("ail"),
            user_id=user_id,
            scene=event.scene,
            purpose=purpose,
            model=event.model or "-",
            provider=event.provider or "-",
            transport=event.transport,
            status=event.status,
            error_code=event.error_code,
            input_tokens=event.input_tokens or None,
            output_tokens=event.output_tokens or None,
            cost_usd=estimate_cost_usd(
                event.model, event.input_tokens, event.output_tokens
            ),
            latency_ms=event.latency_ms,
            fallback_from=event.fallback_from,
        )
        ai_call_log_repository.insert(db, log)
    except Exception:  # noqa: BLE001 — 审计旁路：失败不影响业务
        logger.warning("AI 审计日志写入失败 scene=%s", event.scene, exc_info=True)
        try:
            db.rollback()
        except Exception:  # noqa: BLE001
            logger.warning("AI 审计回滚失败", exc_info=True)

    # 指标与落库解耦：即使 DB 失败也要计数
    metrics.inc_counter("ai_call_total")
    metrics.inc_counter(f"ai_call_total/{event.scene}")
    if event.status != "success":
        metrics.inc_counter("ai_call_error_total")
        metrics.inc_counter(f"ai_call_error_total/{event.scene}")
    metrics.observe("ai_call_latency_ms", event.latency_ms)


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
    """包裹一次 LLM 调用；退出时把事件写入 `ai_call_logs`。

    - `model`/`provider` 为配置值兜底，LLMClient 的实际调用会覆盖事件字段；
    - `AppError` 与未知异常都会记为 `failed` 后原样上抛；
    - `GeneratorExit`（流式消费端提前关闭）不记为失败，只写已完成的用量。
    """
    spec = get_scene(scene)
    event = audit.AuditEvent(
        scene=scene,
        model=model,
        provider=provider,
        transport=transport,
    )
    token = audit.begin(event)
    started = time.monotonic()
    try:
        yield event
    except AppError as exc:
        event.status = "failed"
        event.error_code = exc.error_code
        raise
    except GeneratorExit:
        # 流被消费端提前关闭：不是 provider 失败，按现状落库
        raise
    except Exception as exc:  # noqa: BLE001 — 记录后原样上抛
        event.status = "failed"
        event.error_code = "INTERNAL_ERROR"
        logger.warning(
            "AI 调用异常 scene=%s type=%s", scene, type(exc).__name__
        )
        raise
    finally:
        event.latency_ms = int((time.monotonic() - started) * 1000)
        audit.end(token)
        _write(
            db,
            user_id=user_id,
            event=event,
            purpose=spec.purpose.value if spec.purpose else None,
        )


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
        "latency_ms": event.latency_ms,
    }
