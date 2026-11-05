from __future__ import annotations

import threading

from app.core import metrics


def test_inc_counter_accumulates() -> None:
    metrics.inc_counter("rag_judge_total/true")
    metrics.inc_counter("rag_judge_total/true")
    metrics.inc_counter("rag_judge_total/false")

    snap = metrics.snapshot()
    assert snap["counters"]["rag_judge_total/true"] == 2
    assert snap["counters"]["rag_judge_total/false"] == 1
    assert snap["counters"].get("rag_judge_total/fallback", 0) == 0


def test_inc_counter_thread_safe() -> None:
    def worker() -> None:
        for _ in range(200):
            metrics.inc_counter("scene")

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert metrics.snapshot()["counters"]["scene"] == 800


def test_window_empty_snapshot() -> None:
    snap = metrics.snapshot()["windows"]
    assert snap == {}
    assert metrics.window_percentile("missing", 0.95) is None


def test_window_insufficient_samples_marks_flag() -> None:
    for value in range(5):
        metrics.observe("retrieval_total_ms", float(value))

    window = metrics.snapshot()["windows"]["retrieval_total_ms"]
    assert window["samples"] == 5
    assert window["p50"] is None
    assert window["p95"] is None
    assert window["insufficient"] is True
    assert window["max"] == 4.0
    # 样本不足时告警判定也拿不到分位数
    assert metrics.window_percentile("retrieval_total_ms", 0.95) is None


def test_window_percentile_values() -> None:
    for value in range(1, 101):  # 1..100
        metrics.observe("retrieval_total_ms", float(value))

    assert metrics.window_percentile("retrieval_total_ms", 0.50) == 50.0
    assert metrics.window_percentile("retrieval_total_ms", 0.95) == 95.0

    window = metrics.snapshot()["windows"]["retrieval_total_ms"]
    assert window["samples"] == 100
    assert window["p50"] == 50.0
    assert window["p95"] == 95.0
    assert window["max"] == 100.0
    assert window["insufficient"] is False


def test_window_bounded_by_maxlen() -> None:
    for value in range(1500):
        metrics.observe("retrieval_candidate_rows", float(value))

    window = metrics.snapshot()["windows"]["retrieval_candidate_rows"]
    assert window["samples"] == 1000  # 滑动窗口上限
    assert window["max"] == 1499.0


def test_reset_clears_everything() -> None:
    metrics.inc_counter("x")
    metrics.observe("y", 1.0)
    metrics.reset()

    snap = metrics.snapshot()
    assert snap["counters"] == {}
    assert snap["windows"] == {}


def test_snapshot_never_raises_on_mixed_usage() -> None:
    metrics.inc_counter("a")
    metrics.observe("b", 42.0)
    snap = metrics.snapshot()

    assert snap["counters"]["a"] == 1
    assert snap["windows"]["b"]["samples"] == 1
