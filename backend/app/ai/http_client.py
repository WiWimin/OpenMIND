"""AI 能力层模型客户端的公共 HTTP 基类。

统一实现 `docs/ai-design.md` 约定的调用规则：单次超时、
指数退避 (1, 3) 秒、最多 3 次尝试、429/5xx 可重试、
额度类错误（402 或响应文本命中额度提示词）不可重试。

LLM / Embedding / 音频转写三个客户端共用本基类，
子类只需声明 `service_label`（用于错误文案）并实现具体端点调用。
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from urllib.parse import urlsplit

import httpx

from app.core.exceptions import AppError

logger = logging.getLogger(__name__)

BACKOFF_SECONDS = (1, 3)
MAX_ATTEMPTS = 3

QUOTA_HINTS = ("quota", "balance", "insufficient", "billing", "免费额度", "额度", "余额")


def is_quota_error(response: httpx.Response) -> bool:
    try:
        text = response.text.lower()
    except Exception:
        return False
    return any(hint in text for hint in QUOTA_HINTS)


def log_transport_warning(kind: str, api_base: str, model: str | None, exc: Exception) -> None:
    logger.warning(
        "%s host=%s model=%s type=%s",
        kind,
        urlsplit(api_base).hostname or "invalid",
        model or "-",
        type(exc).__name__,
    )


class ModelHTTPClient:
    """OpenAI 兼容 HTTP 模型客户端基类：持有 httpx.Client、重试循环与错误映射。"""

    service_label = "模型服务"

    def __init__(
        self,
        *,
        api_base: str,
        api_key: str | None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self._client = httpx.Client(base_url=self.api_base, transport=transport)

    def _request_with_retry(
        self,
        send: Callable[[], httpx.Response],
        *,
        model: str | None = None,
        timeout_error: AppError | None = None,
        network_error: AppError | None = None,
    ) -> httpx.Response:
        """带退避的重试循环；`send` 返回非 200 时按 HTTP 错误映射。"""
        last_error: AppError | None = None
        for attempt in range(MAX_ATTEMPTS):
            if attempt:
                time.sleep(BACKOFF_SECONDS[attempt - 1])
            try:
                response = send()
            except httpx.TimeoutException as exc:
                log_transport_warning(f"{self.service_label}超时", self.api_base, model, exc)
                last_error = timeout_error or self._timeout_error()
            except httpx.HTTPError as exc:
                log_transport_warning(
                    f"{self.service_label}网络异常", self.api_base, model, exc
                )
                last_error = network_error or self._network_error()
            else:
                if response.status_code == httpx.codes.OK:
                    return response
                last_error = self.http_error(response)
            if not last_error.retryable:
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
        """把非 200 响应映射为统一 AppError（错误码集合见 docs/api.md 一.3）。"""
        status_code = response.status_code
        if status_code == 429:
            return AppError(
                "RATE_LIMITED", f"{self.service_label}限流", http_status=429, retryable=True
            )
        if 500 <= status_code < 600:
            return AppError(
                "INTERNAL_ERROR",
                f"{self.service_label}暂时不可用",
                http_status=500,
                retryable=True,
            )
        if status_code in (401, 403):
            return AppError(
                "MODEL_CONFIG_INVALID",
                f"{self.service_label}密钥无效或已失效",
                http_status=400,
                retryable=False,
            )
        if status_code == 402 or is_quota_error(response):
            return AppError(
                "MODEL_QUOTA_EXCEEDED",
                f"{self.service_label}额度不足",
                http_status=402,
                retryable=False,
            )
        return AppError(
            "MODEL_CONFIG_INVALID",
            f"{self.service_label}调用失败，请检查配置",
            http_status=400,
            retryable=False,
        )
