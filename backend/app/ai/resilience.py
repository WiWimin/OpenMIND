"""AI 调用的并发保护与熔断（`ai-design.md 3.6`）。

目标：单一 provider 故障时快速失败、限制在途请求，避免故障放大打穿本服务。

- **并发闸门 `ProviderGate`**：按 `api_base` 限制在途请求数（进程内信号量，
  同步 `threading.Semaphore` + 异步轮询复用同一计数，保证两条路径共享额度）。
  排队超时 → `RATE_LIMITED`（429，`details.scope="concurrency"`）。
- **熔断器 `CircuitBreaker`**：按 `api_base|model` 统计近期失败（5xx / 超时 /
  传输中断），达到阈值后进入 open：直接抛 `MODEL_UPSTREAM_UNAVAILABLE`（503，
  可重试），`AI_CIRCUIT_OPEN_SECONDS` 后放行 1 个探针（half-open），探针成功即闭合。
  密钥/额度/参数类错误（4xx）不计入失败——provider 是健康的。
- 单实例进程内状态（与 `core/rate_limit.py` 同口径：多 worker/多实例不共享）；
  `reset()` 供测试清零。
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from collections import deque
from collections.abc import Callable

from app.core.config import get_settings
from app.core.exceptions import AppError

logger = logging.getLogger(__name__)

# 异步轮询闸门的间隔（秒）：不阻塞事件循环，也不过度空转
_ASYNC_POLL_S = 0.02


def _enabled() -> bool:
    return get_settings().ai_resilience_enabled


def gate_key(api_base: str) -> str:
    """并发闸门维度：同一 API 地址共享额度。"""
    return api_base


def breaker_key(api_base: str, model: str | None) -> str:
    """熔断维度：不同模型的健康度独立统计（主模型故障不影响备用模型）。"""
    return f"{api_base}|{model or '-'}"


class ProviderGate:
    """按 key 限制在途请求数的进程内信号量。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._semaphores: dict[str, threading.BoundedSemaphore] = {}

    def _semaphore(self, key: str, limit: int) -> threading.BoundedSemaphore:
        with self._lock:
            sem = self._semaphores.get(key)
            if sem is None:
                sem = threading.BoundedSemaphore(max(1, limit))
                self._semaphores[key] = sem
            return sem

    def acquire(self, key: str, *, timeout_s: float) -> bool:
        """同步获取一个在途名额；超时返回 False（调用方转 429）。"""
        if not _enabled():
            return True
        limit = get_settings().ai_max_concurrency_per_provider
        return self._semaphore(key, limit).acquire(timeout=max(0.0, timeout_s))

    async def aacquire(self, key: str, *, timeout_s: float) -> bool:
        """异步获取：轮询同一个线程安全信号量，不阻塞事件循环。"""
        if not _enabled():
            return True
        deadline = time.monotonic() + max(0.0, timeout_s)
        while True:
            if self.try_acquire(key):
                return True
            if time.monotonic() >= deadline:
                return False
            await asyncio.sleep(_ASYNC_POLL_S)

    def try_acquire(self, key: str) -> bool:
        if not _enabled():
            return True
        limit = get_settings().ai_max_concurrency_per_provider
        return self._semaphore(key, limit).acquire(blocking=False)

    def release(self, key: str) -> None:
        """释放名额；未持有时调用仅记 warning（信号量值可能已重建）。"""
        with self._lock:
            sem = self._semaphores.get(key)
        if sem is None:
            return
        try:
            sem.release()
        except ValueError:  # 超额释放：测试重建过信号量
            logger.debug("并发名额超额释放 key=%s", key)

    def reset(self) -> None:
        with self._lock:
            self._semaphores.clear()


class CircuitBreaker:
    """按 key 的失败计数熔断：closed → open → half_open（单探针）→ closed。"""

    def __init__(self, *, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._lock = threading.Lock()
        self._states: dict[str, str] = {}
        self._failures: dict[str, deque[float]] = {}
        self._open_until: dict[str, float] = {}
        self._probing: set[str] = set()

    def check(self, key: str) -> None:
        """调用前检查；熔断打开时抛 `MODEL_UPSTREAM_UNAVAILABLE`。"""
        if not _enabled():
            return
        now = self._clock()
        with self._lock:
            state = self._states.get(key, "closed")
            if state == "open":
                if now < self._open_until.get(key, 0.0):
                    raise self._open_error(key)
                # 到点放行 1 个探针
                self._states[key] = "half_open"
                self._probing.add(key)
                return
            if state == "half_open":
                if key in self._probing:
                    raise self._open_error(key)
                self._probing.add(key)
                return

    def record_success(self, key: str) -> None:
        """探针/正常调用成功 → 闭合并清零失败计数。"""
        if not _enabled():
            return
        with self._lock:
            self._states.pop(key, None)
            self._failures.pop(key, None)
            self._open_until.pop(key, None)
            self._probing.discard(key)

    def record_failure(self, key: str) -> None:
        """记录一次 provider 侧失败（5xx/超时/传输中断）。"""
        if not _enabled():
            return
        settings = get_settings()
        now = self._clock()
        with self._lock:
            if self._states.get(key) == "half_open":
                # 探针失败 → 立即重新打开
                self._probing.discard(key)
                self._failures.pop(key, None)
                self._open_until[key] = now + settings.ai_circuit_open_seconds
                self._states[key] = "open"
                logger.warning("熔断探针失败，重新打开 provider=%s", key)
                return
            failures = self._failures.get(key)
            if failures is None:
                failures = deque()
                self._failures[key] = failures
            cutoff = now - settings.ai_circuit_window_seconds
            while failures and failures[0] <= cutoff:
                failures.popleft()
            failures.append(now)
            if len(failures) >= max(1, settings.ai_circuit_failure_threshold):
                self._states[key] = "open"
                self._open_until[key] = now + settings.ai_circuit_open_seconds
                self._failures.pop(key, None)
                logger.warning(
                    "熔断打开 provider=%s failures_threshold=%d open_s=%.0f",
                    key,
                    settings.ai_circuit_failure_threshold,
                    settings.ai_circuit_open_seconds,
                )

    @staticmethod
    def _open_error(key: str) -> AppError:
        return AppError(
            "MODEL_UPSTREAM_UNAVAILABLE",
            "模型服务暂时不可用，请稍后重试",
            http_status=503,
            retryable=True,
            details={"circuit": "open", "provider": key.split("|", 1)[0]},
        )

    def state(self, key: str) -> str:
        with self._lock:
            return self._states.get(key, "closed")

    def reset(self) -> None:
        with self._lock:
            self._states.clear()
            self._failures.clear()
            self._open_until.clear()
            self._probing.clear()


_gate = ProviderGate()
_breaker = CircuitBreaker()


def get_gate() -> ProviderGate:
    return _gate


def get_breaker() -> CircuitBreaker:
    return _breaker


def reset() -> None:
    """清空闸门与熔断状态（仅供测试）。"""
    _gate.reset()
    _breaker.reset()
