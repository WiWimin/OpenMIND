from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import case, func, select, update
from sqlalchemy.orm import Session

from app.models.ai_call_log import AICallLog

# 统计聚合的四舍五入位数（与 cost_usd NUMERIC(12,6) 对齐）
_COST_QUANTUM = Decimal("0.000001")


def insert(db: Session, log: AICallLog) -> None:
    """预创建一条 `running` 审计行并提交（`ai_audit_service.persist_start`）。

    调用方约束：预创建发生在纯 LLM 调用段开始时，此时会话内没有未提交的
    业务写入，提交审计行不会连带提交业务状态。
    """
    db.add(log)
    db.commit()


def finish(
    db: Session,
    log_id: str,
    *,
    status: str,
    error_code: str | None,
    model: str,
    provider: str,
    input_tokens: int | None,
    output_tokens: int | None,
    cost_usd: Decimal | None,
    latency_ms: int,
    fallback_from: str | None,
    fallback_scope: str | None,
    meta: dict[str, Any],
    finished_at: datetime,
) -> bool:
    """把预创建行更新为终态并提交；行不存在（已被回收/删除）返回 False。"""
    log = db.get(AICallLog, log_id)
    if log is None:
        return False
    log.status = status
    log.error_code = error_code
    log.model = model
    log.provider = provider
    log.input_tokens = input_tokens
    log.output_tokens = output_tokens
    log.cost_usd = cost_usd
    log.latency_ms = latency_ms
    log.fallback_from = fallback_from
    log.fallback_scope = fallback_scope
    log.meta = meta
    log.finished_at = finished_at
    db.commit()
    return True


def list_by_user(
    db: Session, user_id: str, *, scene: str | None = None, limit: int = 100
) -> list[AICallLog]:
    """按用户倒序取审计日志（运维/排障用；MVP 不对外暴露接口）。"""
    stmt = select(AICallLog).where(AICallLog.user_id == user_id)
    if scene:
        stmt = stmt.where(AICallLog.scene == scene)
    stmt = stmt.order_by(AICallLog.created_at.desc()).limit(limit)
    return list(db.execute(stmt).scalars())


def reap_running(db: Session, *, cutoff: datetime, finished_at: datetime) -> int:
    """把超窗未收尾的 `running` 行兜底为 `failed AI_CALL_INTERRUPTED`。"""
    stmt = (
        update(AICallLog)
        .where(AICallLog.status == "running", AICallLog.created_at < cutoff)
        .values(
            status="failed",
            error_code="AI_CALL_INTERRUPTED",
            finished_at=finished_at,
        )
        .execution_options(synchronize_session=False)
    )
    result = db.execute(stmt)
    db.commit()
    return int(result.rowcount or 0)


def _cost(value: Any) -> Decimal | None:
    if value is None:
        return None
    return Decimal(value).quantize(_COST_QUANTUM)


def aggregate(db: Session, *, since: datetime) -> dict[str, Any]:
    """按时间窗聚合审计行（持久化统计；供 `/metrics` 的 `ai_calls` 段）。

    只返回数值与枚举标签（日志红线）；`cost_usd` 为估算值，非计费依据。
    """
    where = [AICallLog.created_at >= since]
    failed = case((AICallLog.status == "failed", 1), else_=0)

    total = (
        db.execute(select(func.count(AICallLog.log_id)).where(*where)).scalar() or 0
    )
    error_total = (
        db.execute(select(func.coalesce(func.sum(failed), 0)).where(*where)).scalar()
        or 0
    )

    status_rows = db.execute(
        select(AICallLog.status, func.count(AICallLog.log_id))
        .where(*where)
        .group_by(AICallLog.status)
    ).all()
    by_status = {str(status): int(count) for status, count in status_rows}

    scene_rows = db.execute(
        select(
            AICallLog.scene,
            func.count(AICallLog.log_id),
            func.coalesce(func.sum(failed), 0),
            func.coalesce(func.sum(AICallLog.input_tokens), 0),
            func.coalesce(func.sum(AICallLog.output_tokens), 0),
            func.sum(AICallLog.cost_usd),
            func.avg(AICallLog.latency_ms),
        )
        .where(*where)
        .group_by(AICallLog.scene)
        .order_by(func.count(AICallLog.log_id).desc())
    ).all()
    by_scene = [
        {
            "scene": str(name),
            "count": int(count),
            "errors": int(errors),
            "input_tokens": int(tin or 0),
            "output_tokens": int(tout or 0),
            "cost_usd": _cost(cost),
            "avg_latency_ms": round(float(avg_latency), 1) if avg_latency else 0,
        }
        for name, count, errors, tin, tout, cost, avg_latency in scene_rows
    ]

    model_rows = db.execute(
        select(
            AICallLog.model,
            func.count(AICallLog.log_id),
            func.coalesce(func.sum(failed), 0),
            func.sum(AICallLog.cost_usd),
        )
        .where(*where)
        .group_by(AICallLog.model)
        .order_by(func.count(AICallLog.log_id).desc())
    ).all()
    by_model = [
        {
            "model": str(name),
            "count": int(count),
            "errors": int(errors),
            "cost_usd": _cost(cost),
        }
        for name, count, errors, cost in model_rows
    ]

    totals = db.execute(
        select(
            func.coalesce(func.sum(AICallLog.input_tokens), 0),
            func.coalesce(func.sum(AICallLog.output_tokens), 0),
            func.sum(AICallLog.cost_usd),
            func.avg(AICallLog.latency_ms),
            func.max(AICallLog.latency_ms),
        ).where(*where)
    ).one()
    tin, tout, cost, avg_latency, max_latency = totals

    return {
        "total": int(total),
        "by_status": by_status,
        "by_scene": by_scene,
        "by_model": by_model,
        "tokens": {"input": int(tin or 0), "output": int(tout or 0)},
        "cost_usd": _cost(cost),
        "latency_ms": {
            "avg": round(float(avg_latency), 1) if avg_latency else 0,
            "max": int(max_latency or 0),
        },
        "errors": {
            "total": int(error_total),
            "rate": round(error_total / total, 4) if total else 0.0,
        },
        "running": int(by_status.get("running", 0)),
        "interrupted": int(
            db.execute(
                select(func.count(AICallLog.log_id)).where(
                    *where, AICallLog.error_code == "AI_CALL_INTERRUPTED"
                )
            ).scalar()
            or 0
        ),
    }
