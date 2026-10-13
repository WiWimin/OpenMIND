from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx
from pydantic import BaseModel, ValidationError

from app.core.config import get_settings
from app.core.exceptions import AppError

logger = logging.getLogger(__name__)

_BACKOFF_SECONDS = (1, 3)
_MAX_ATTEMPTS = 3


@dataclass(frozen=True)
class LLMResult:
    text: str
    model: str
    usage: dict[str, int]
    latency_ms: int


class LLMClient:
    def __init__(
        self,
        *,
        api_base: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        settings = get_settings()
        self.api_base = (api_base or settings.llm_api_base).rstrip("/")
        self.api_key = api_key or settings.llm_api_key
        self.model = model or settings.llm_model
        self._client = httpx.Client(base_url=self.api_base, transport=transport)

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        timeout_s: float = 60,
        response_format: dict[str, Any] | None = None,
    ) -> LLMResult:
        self._ensure_configured()
        payload: dict[str, Any] = {
            "model": model or self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if response_format is not None:
            payload["response_format"] = response_format

        started = time.monotonic()
        last_error: AppError | None = None
        for attempt in range(_MAX_ATTEMPTS):
            if attempt:
                time.sleep(_BACKOFF_SECONDS[attempt - 1])
            try:
                response = self._client.post(
                    "/chat/completions",
                    json=payload,
                    headers=self._headers(),
                    timeout=timeout_s,
                )
            except httpx.TimeoutException:
                last_error = self._timeout_error()
            except httpx.HTTPError:
                last_error = self._network_error()
            else:
                if response.status_code == httpx.codes.OK:
                    elapsed_ms = int((time.monotonic() - started) * 1000)
                    return self._parse_result(response, model or self.model, elapsed_ms)
                last_error = self._http_error(response)
            if not last_error.retryable:
                raise last_error
        raise last_error or self._network_error()

    def chat_json(
        self,
        messages: list[dict[str, str]],
        *,
        schema: type[BaseModel],
        model: str | None = None,
        **kwargs: Any,
    ) -> BaseModel:
        kwargs.setdefault("response_format", {"type": "json_object"})
        result = self.chat(messages, model=model, **kwargs)
        try:
            return schema.model_validate_json(result.text)
        except ValidationError:
            raise AppError(
                "MODEL_OUTPUT_INVALID",
                "模型输出无法解析",
                http_status=502,
                retryable=False,
            ) from None

    def _ensure_configured(self) -> None:
        if not self.api_base or not self.api_key:
            raise AppError(
                "INTERNAL_ERROR",
                "模型服务未配置",
                http_status=500,
                retryable=False,
            )

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _timeout_error(self) -> AppError:
        return AppError("MODEL_TIMEOUT", "模型调用超时", http_status=504, retryable=True)

    def _network_error(self) -> AppError:
        return AppError(
            "INTERNAL_ERROR",
            "模型服务网络异常",
            http_status=500,
            retryable=True,
        )

    def _http_error(self, response: httpx.Response) -> AppError:
        status_code = response.status_code
        if status_code == 429:
            return AppError("RATE_LIMITED", "模型服务限流", http_status=429, retryable=True)
        if 500 <= status_code < 600:
            return AppError(
                "INTERNAL_ERROR",
                "模型服务异常",
                http_status=500,
                retryable=True,
            )
        return AppError(
            "INTERNAL_ERROR",
            "模型服务调用失败",
            http_status=500,
            retryable=False,
        )

    def _parse_result(self, response: httpx.Response, model: str, elapsed_ms: int) -> LLMResult:
        try:
            data = response.json()
        except ValueError:
            raise AppError(
                "MODEL_OUTPUT_INVALID",
                "模型输出无法解析",
                http_status=502,
                retryable=False,
            ) from None
        choices = data.get("choices") or []
        if not choices:
            raise AppError("MODEL_OUTPUT_INVALID", "模型输出为空", http_status=502, retryable=False)
        content = (choices[0].get("message") or {}).get("content")
        if not content:
            raise AppError("MODEL_OUTPUT_INVALID", "模型输出为空", http_status=502, retryable=False)
        usage = data.get("usage") or {}
        result = LLMResult(
            text=content,
            model=data.get("model") or model,
            usage={
                "input": int(usage.get("prompt_tokens") or 0),
                "output": int(usage.get("completion_tokens") or 0),
            },
            latency_ms=elapsed_ms,
        )
        logger.info(
            "LLM 调用成功 model=%s latency_ms=%d usage=%s",
            result.model,
            result.latency_ms,
            result.usage,
        )
        return result
