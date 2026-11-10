"""AI 能力层模型客户端的公共 HTTP 基类。

统一实现 `docs/ai-design.md 3.2` 约定的调用规则：

- **连接池复用**：按 `api_base` 共享 `httpx.Client`（见 `app/ai/connection.py`）；
- **分级重试**：按幂等性决定是否重传「已送达但未收到响应」的失败
 （非幂等的 chat/ASR 不重传读超时与传输中断，避免重复扣费）；
- **退避与限速**：指数退避 + 抖动，尊重 `Retry-After`，全局 deadline 截断总耗时；
- 错误映射：429 → `RATE_LIMITED`（带 `details.retry_after_s`）、5xx → `INTERNAL_ERROR`、
  401/403 → `MODEL_CONFIG_INVALID`、402 或响应文本命中额度提示词 → `MODEL_QUOTA_EXCEEDED`。

LLM / Embedding / 音频转写三个客户端共用本基类，子类声明 `service_label`
（错误文案）与 `idempotent`（幂等性），并实现具体端点调用。
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from urllib.parse import urlsplit

import httpx

from app.ai import connection, resilience
from app.ai import errors as ai_errors
from app.ai.retry import (
    BACKOFF_SECONDS,
    MAX_ATTEMPTS,
    RetryPolicy,
    parse_retry_after,
)
from app.core import metrics
from app.core.config import get_settings
from app.core.exceptions import AppError

# 供 `tests/unit/test_llm_stream.py` 等按模块路径 monkeypatch 的常量（保持向后兼容）
__all__ = [
    "BACKOFF_SECONDS",
    "MAX_ATTEMPTS",
    "ModelHTTPClient",
    "app_error_kind",
    "classify_transport_error",
    "is_quota_error",
]

logger = logging.getLogger(__name__)

# 单次发送：接收本次尝试的超时预算（受全局 deadline 收窄）
Sender = Callable[[float], httpx.Response]


def is_quota_error(response: httpx.Response) -> bool:
    """兼容导出：额度判定已移至 `app/ai/errors.py`。"""
    return ai_errors.is_quota_error(response)


def log_transport_warning(kind: str, api_base: str, model: str | None, exc: Exception) -> None:
    logger.warning(
        "%s host=%s model=%s type=%s",
        kind,
        urlsplit(api_base).hostname or "invalid",
        model or "-",
        type(exc).__name__,
    )


def classify_transport_error(exc: Exception) -> str:
    """把传输层异常归类为重试级别：connect（未送达）/ timeout / transport（已送达未知）。"""
    if isinstance(exc, httpx.ConnectError) or isinstance(exc, httpx.ConnectTimeout):
        return "connect"
    if isinstance(exc, httpx.TimeoutException):
        return "timeout"
    return "transport"


def app_error_kind(exc: AppError) -> str:
    """把统一 `AppError` 映射回重试级别（供流式等旁路重试循环复用同一策略）。"""
    if exc.error_code == "MODEL_TIMEOUT":
        return "timeout"
    if exc.error_code == "RATE_LIMITED":
        return "http_429"
    if exc.error_code == "INTERNAL_ERROR":
        return "http_5xx"
    return "http"


class ModelHTTPClient:
    """OpenAI 兼容 HTTP 模型客户端基类：共享连接池、重试循环与错误映射。"""

    service_label = "模型服务"
    # 幂等性：True = 重复请求不产生重复计费风险，可安全重试读超时/传输中断
    idempotent: bool = True

    def __init__(
        self,
        *,
        api_base: str,
        api_key: str | None,
        transport: httpx.BaseTransport | None = None,
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self._transport = transport
        # 注入 transport 的是测试客户端（MockTransport），不进池
        self._client = connection.get_sync_client(self.api_base, transport=transport)
        self.retry_policy = retry_policy or RetryPolicy(
            max_attempts=MAX_ATTEMPTS, retry_ambiguous=self.idempotent
        )

    def _request_with_retry(
        self,
        send: Sender,
        *,
        model: str | None = None,
        timeout_s: float | None = None,
        timeout_error: AppError | None = None,
        network_error: AppError | None = None,
    ) -> httpx.Response:
        """带分级重试的发送循环：`send(本次尝试的超时预算)` 返回非 200 时按 HTTP 错误映射。"""
        policy = self.retry_policy
        deadline_at = (
            time.monotonic() + policy.deadline_s if policy.deadline_s is not None else None
        )
        last_error: AppError | None = None
        retry_after_s: float | None = None
        kind = "unknown"
        settings = get_settings()
        gate = resilience.get_gate()
        breaker = resilience.get_breaker()
        gkey = resilience.gate_key(self.api_base)
        bkey = resilience.breaker_key(self.api_base, model)

        for attempt in range(policy.max_attempts):
            if attempt:
                delay = policy.delay_for(attempt, retry_after_s=retry_after_s)
                retry_after_s = None
                if deadline_at is not None and time.monotonic() + delay >= deadline_at:
                    logger.warning(
                        "模型调用超出全局 deadline，停止重试 host=%s model=%s attempts=%d",
                        urlsplit(self.api_base).hostname or "invalid",
                        model or "-",
                        attempt,
                    )
                    raise last_error or self._timeout_error()
                time.sleep(delay)

            # deadline 的起算与消耗必须用同一时钟源（测试会替换本模块的 time）
            remaining = deadline_at - time.monotonic() if deadline_at is not None else None
            if remaining is not None and remaining <= 0.05:
                logger.warning(
                    "模型调用 deadline 已耗尽 host=%s model=%s",
                    urlsplit(self.api_base).hostname or "invalid",
                    model or "-",
                )
                raise last_error or self._timeout_error()
            attempt_timeout = timeout_s
            if remaining is not None:
                attempt_timeout = min(timeout_s, remaining) if timeout_s else remaining

            # 熔断先于排队检查：打开时直接快速失败，不占用并发名额
            try:
                breaker.check(bkey)
            except AppError:
                metrics.inc_counter("ai_circuit_open_total")
                raise
            if not gate.acquire(gkey, timeout_s=settings.ai_concurrency_timeout_s):
                metrics.inc_counter("ai_concurrency_rejected_total")
                raise AppError(
                    "RATE_LIMITED",
                    f"{self.service_label}并发已满，请稍后重试",
                    http_status=429,
                    retryable=True,
                    details={"scope": "concurrency"},
                )
            # 通过闸门后才真正发出（可能被熔断/并发拒绝拦下，不算重试）
            if attempt:
                metrics.inc_counter("ai_retry_total")
            try:
                try:
                    response = send(attempt_timeout)
                except httpx.TimeoutException as exc:
                    kind = classify_transport_error(exc)
                    log_transport_warning(
                        f"{self.service_label}超时", self.api_base, model, exc
                    )
                    last_error = timeout_error or self._timeout_error()
                    breaker.record_failure(bkey)
                except httpx.HTTPError as exc:
                    kind = classify_transport_error(exc)
                    log_transport_warning(
                        f"{self.service_label}网络异常", self.api_base, model, exc
                    )
                    last_error = network_error or self._network_error()
                    breaker.record_failure(bkey)
                else:
                    if response.status_code == httpx.codes.OK:
                        breaker.record_success(bkey)
                        return response
                    status = response.status_code
                    last_error = self.http_error(response)
                    if status == httpx.codes.TOO_MANY_REQUESTS:
                        kind = "http_429"
                        retry_after_s = parse_retry_after(
                            response.headers.get("retry-after")
                        )
                    elif 500 <= status < 600:
                        kind = "http_5xx"
                        breaker.record_failure(bkey)
                    else:
                        # 429/4xx 属于请求侧或限流问题，provider 本身健康，不计入熔断
                        kind = "http"
            finally:
                gate.release(gkey)

            if not policy.allows(kind, retryable=last_error.retryable):
                raise last_error
        raise last_error or self._network_error()

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _timeout_error(self) -> AppError:
        return AppError(
            "MODEL_TIMEOUT", f"{self.service_label}超时", http_status=504, retryable=True
        )

    def _network_error(self) -> AppError:
        return AppError(
            "INTERNAL_ERROR",
            f"{self.service_label}网络异常",
            http_status=500,
            retryable=True,
        )

    def http_error(self, response: httpx.Response) -> AppError:
        """把非 200 响应映射为统一 AppError（细分实现见 `app/ai/errors.py`）。"""
        return ai_errors.classify_error(response, service_label=self.service_label)
