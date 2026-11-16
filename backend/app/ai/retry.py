"""模型调用的重试策略：分级重试、抖动退避、Retry-After 与全局 deadline。

对应 `docs/ai-design.md 3.2`：

- 最多 3 次尝试，指数退避（基数 1s、封顶 3s）并叠加 0.5–1.5 倍随机抖动，
  避免多实例/多连接同时重试形成踩踏；
- **按幂等性分级重试**：`connect`（连接建立失败，请求未送达）可重试；
  `timeout`（读超时）/ `transport`（传输中断）属于「已送达但未收到响应」，
  对非幂等请求（chat 补全、ASR 转写）**不重传**，避免重复计费；
- 尊重服务端 `Retry-After`（秒数或 HTTP-date），实际等待取
  `max(退避, Retry-After)`，并受全局 deadline 约束；
- 全局 deadline：单次超时取 `min(单次超时, 剩余 deadline)`，剩余不足时
  直接返回最后一次错误，防止重试把总耗时穿透网关/前端超时。
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass
from email.utils import parsedate_to_datetime

# 指数退避基数与封顶（秒）：第 n 次重试等待 base * 2**(n-1)，再乘抖动
BACKOFF_SECONDS = (1.0, 3.0)
# 最多 3 次尝试（2 次重试）
MAX_ATTEMPTS = 3
# 抖动区间倍率（0.5–1.5 倍）
_JITTER_MIN = 0.5
_JITTER_SPAN = 1.0
# 服务端 Retry-After 的采纳上限（秒）：异常大的值不用于本地等待，
# 交由 deadline 截断并把 RATE_LIMITED 直接抛给调用方
MAX_RETRY_AFTER_S = 30.0
# 剩余 deadline 少于该值时不再发起新尝试（秒）
_MIN_REMAINING_S = 0.05


def parse_retry_after(value: str | None, *, now: float | None = None) -> float | None:
    """解析 `Retry-After` 头（秒数或 HTTP-date），返回非负秒数；无法解析返回 None。"""
    text = (value or "").strip()
    if not text:
        return None
    seconds: float
    try:
        seconds = float(text)
    except ValueError:
        try:
            parsed = parsedate_to_datetime(text)
        except (TypeError, ValueError, OverflowError):
            return None
        if parsed is None:
            return None
        base = time.time() if now is None else now
        seconds = parsed.timestamp() - base
    if seconds < 0:
        return None
    return min(seconds, MAX_RETRY_AFTER_S)


@dataclass(frozen=True)
class RetryPolicy:
    """一次模型调用的重试策略。

    - `deadline_s`：整次调用（含重试与退避）的总时长预算；
      `None` 表示不限制（仅受单次超时约束）。
    - `retry_connect`：连接建立失败（请求未送达）是否重试，默认允许。
    - `retry_ambiguous`：读超时/传输中断（请求可能已被服务商处理并计费）
      是否重试，**非幂等调用必须为 False**。
    """

    max_attempts: int = MAX_ATTEMPTS
    backoff_base_s: float = BACKOFF_SECONDS[0]
    backoff_cap_s: float = BACKOFF_SECONDS[1]
    deadline_s: float | None = None
    retry_connect: bool = True
    retry_ambiguous: bool = False
    retry_429: bool = True
    retry_5xx: bool = True

    def allows(self, kind: str, *, retryable: bool = True) -> bool:
        """判断失败类别是否允许重试；`retryable` 为错误体语义（401/402 永不重试）。"""
        if not retryable:
            return False
        if kind == "connect":
            return self.retry_connect
        if kind in ("timeout", "transport"):
            return self.retry_ambiguous
        if kind == "http_429":
            return self.retry_429
        if kind == "http_5xx":
            return self.retry_5xx
        return False

    def delay_for(
        self,
        attempt: int,
        *,
        retry_after_s: float | None = None,
        rng: random.Random | None = None,
    ) -> float:
        """第 `attempt` 次重试（从 1 开始）前的等待秒数。

        公式：`min(cap, base * (2^n - 1)) * 抖动(0.5–1.5)`，
        默认即第 1 次 1s、第 2 次 3s、之后封顶 3s（对齐 `ai-design.md 3.2`）。
        """
        base = min(self.backoff_cap_s, self.backoff_base_s * (2**attempt - 1))
        roll = rng.random() if rng is not None else random.random()
        delay = base * (_JITTER_MIN + _JITTER_SPAN * roll)
        if retry_after_s is not None:
            delay = max(delay, min(retry_after_s, MAX_RETRY_AFTER_S))
        return delay
