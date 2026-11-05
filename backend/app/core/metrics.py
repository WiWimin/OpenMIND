"""轻量内存指标：结构化日志之外的进程内计数与耗时窗口。

- 计数器（counter）：如 RAG Judge 判定结果分布，用于统计触发量与占比；
- 滑动窗口（deque）：如检索各阶段耗时、候选行数，用于计算 P50/P95/max；
- 纯内存、进程重启清零；快照经 `GET /api/v1/metrics` 暴露。

日志红线同样适用：这里只存数值与枚举标签，不存查询原文、提示词或用户内容。
"""

from __future__ import annotations

import threading
from collections import deque
from statistics import mean, median
from typing import Any

# 耗时/计数窗口保留的样本数（约最近 N 次检索）
_WINDOW_SIZE = 1000
# 样本数不足该值时不给出分位数（避免误导性结论）
_MIN_SAMPLES_FOR_PERCENTILE = 20

_lock = threading.Lock()
_counters: dict[str, int] = {}
_windows: dict[str, deque[float]] = {}


def inc_counter(name: str, *, amount: int = 1) -> None:
    """计数器累加（线程安全）。"""
    with _lock:
        _counters[name] = _counters.get(name, 0) + amount


def observe(name: str, value: float) -> None:
    """记录一个耗时/数值样本进滑动窗口（线程安全，超出窗口丢弃最旧样本）。"""
    with _lock:
        window = _windows.get(name)
        if window is None:
            window = deque(maxlen=_WINDOW_SIZE)
            _windows[name] = window
        window.append(float(value))


def _percentile(sorted_values: list[float], fraction: float) -> float:
    """最近秩（nearest-rank）分位数：ceil(fraction * n) 处的样本。"""
    if not sorted_values:
        return 0.0
    rank = max(1, int(len(sorted_values) * fraction + 0.9999))
    return sorted_values[min(rank, len(sorted_values)) - 1]


def _window_snapshot(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"samples": 0, "p50": None, "p95": None, "max": None, "insufficient": True}
    ordered = sorted(values)
    insufficient = len(ordered) < _MIN_SAMPLES_FOR_PERCENTILE
    return {
        "samples": len(ordered),
        "p50": None if insufficient else round(_percentile(ordered, 0.50), 3),
        "p95": None if insufficient else round(_percentile(ordered, 0.95), 3),
        "max": round(ordered[-1], 3),
        "mean": round(mean(ordered), 3),
        "median": round(median(ordered), 3),
        "insufficient": insufficient,
    }


def window_percentile(name: str, fraction: float) -> float | None:
    """取窗口分位数（样本不足时返回 None）——供阈值告警判定使用。"""
    with _lock:
        window = _windows.get(name)
        values = sorted(window) if window else []
    if len(values) < _MIN_SAMPLES_FOR_PERCENTILE:
        return None
    return _percentile(values, fraction)


def snapshot() -> dict[str, Any]:
    """全量指标快照（结构化日志 + 内存端点共用）。"""
    with _lock:
        counters = dict(_counters)
        windows = {name: list(window) for name, window in _windows.items()}
    return {
        "counters": dict(sorted(counters.items())),
        "windows": {name: _window_snapshot(values) for name, values in sorted(windows.items())},
    }


def reset() -> None:
    """清空全部指标（仅供测试使用）。"""
    with _lock:
        _counters.clear()
        _windows.clear()
