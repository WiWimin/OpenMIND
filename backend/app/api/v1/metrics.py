from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter

from app.ai.rag.retriever import alert_marks
from app.core import metrics

router = APIRouter(tags=["ops"])

# 告警状态来源（与 retriever 共用冷却记录）
_JUDGE_COUNTER_KEYS = ("rag_judge_total/true", "rag_judge_total/false", "rag_judge_total/fallback")


@router.get("/metrics")
def read_metrics() -> dict[str, Any]:
    """运维指标快照（无鉴权，建议仅内网暴露）：Judge 判定分布 + 检索耗时/候选行数分位数。

    - 计数器为进程内累计（重启清零）；
    - 分位数来自滑动窗口（约最近 1000 次），样本 < 20 时 `p50/p95` 为 null 并标 `insufficient`；
    - 日志红线同样适用：不含查询原文、提示词与用户内容。
    """
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
        "alerts": {
            "last_fired_monotonic": alert_marks(),
        },
    }
