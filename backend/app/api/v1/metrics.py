from __future__ import annotations

import logging
import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Query

from app.ai.rag.retriever import alert_marks
from app.api.deps import CurrentUser, DbSession
from app.core import metrics
from app.core.config import get_settings
from app.core.exceptions import resource_not_found
from app.repositories import ai_call_log_repository
from app.services import ai_audit_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ops"])

# 告警状态来源（与 retriever 共用冷却记录）
_JUDGE_COUNTER_KEYS = ("rag_judge_total/true", "rag_judge_total/false", "rag_judge_total/fallback")

# 成本序列化位数（与 ai_call_logs.cost_usd NUMERIC(12,6) 对齐；估算值非计费依据）
_COST_QUANTUM = Decimal("0.000001")


def _cost_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(Decimal(value).quantize(_COST_QUANTUM))


def _serialize_ai_calls(section: dict[str, Any]) -> dict[str, Any]:
    """`cost_usd` 统一转字符串，避免浮点误差进入运维视图。"""
    section["cost_usd"] = _cost_str(section.get("cost_usd"))
    for group in ("by_scene", "by_model"):
        for row in section.get(group, []):
            row["cost_usd"] = _cost_str(row.get("cost_usd"))
    return section


def _ai_calls_section(db: DbSession, hours: int) -> dict[str, Any]:
    """持久化统计（`ai_call_logs` 聚合）；读取前懒回收超窗的 running 行。"""
    try:
        ai_audit_service.reap_stale_running(db)
    except Exception:  # noqa: BLE001 — 回收失败不阻断指标读取
        logger.warning("审计行懒回收失败", exc_info=True)
        try:
            db.rollback()
        except Exception:  # noqa: BLE001
            logger.warning("审计行懒回收回滚失败", exc_info=True)

    since = datetime.now(UTC) - timedelta(hours=hours)
    aggregate = ai_call_log_repository.aggregate(db, since=since)
    return _serialize_ai_calls(
        {"window_hours": hours, "since": since.isoformat(), **aggregate}
    )


@router.get("/metrics")
def read_metrics(
    current_user: CurrentUser,
    db: DbSession,
    hours: int = Query(24, ge=1, le=168),
) -> dict[str, Any]:
    """运维指标快照（需登录；METRICS_ENABLED=false 时返回 404 隐藏）。

    内容：进程内计数器（Judge 分布、检索耗时分位数、`ai_*` 埋点）+
    **持久化调用统计**（`ai_call_logs` 近 `hours` 小时聚合）。

    - 计数器为进程内累计（重启清零）；`ai_calls` 来自数据库（重启保留）；
    - 分位数来自滑动窗口（约最近 1000 次），样本 < 20 时 `p50/p95` 为 null 并标 `insufficient`；
    - `ai_calls.cost_usd` 为估算值（见 `ai/pricing.py`），**非计费依据**；
    - 日志红线同样适用：不含查询原文、提示词与用户内容。
    - 生产环境建议配合反向代理限制仅内网可达。
    """
    if not get_settings().metrics_enabled:
        raise resource_not_found("指标")
    snap = metrics.snapshot()
    counters = snap["counters"]
    judge = {
        "true": counters.get(_JUDGE_COUNTER_KEYS[0], 0),
        "false": counters.get(_JUDGE_COUNTER_KEYS[1], 0),
        "fallback": counters.get(_JUDGE_COUNTER_KEYS[2], 0),
    }
    triggered = judge["true"] + judge["false"] + judge["fallback"]
    judge_section: dict[str, Any] = {"triggered": triggered, **judge}
    if triggered:
        judge_section["ratios"] = {
            key: round(value / triggered, 4) for key, value in judge.items()
        }

    return {
        "generated_at": time.time(),
        "counters": counters,
        "rag_judge": judge_section,
        "windows": snap["windows"],
        "ai_calls": _ai_calls_section(db, hours),
        "alerts": {
            "last_fired_monotonic": alert_marks(),
        },
    }
