from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, ValidationError

from app.ai.http_client import ModelHTTPClient
from app.ai.structured import normalize_json_text, validation_error_summary
from app.core.config import get_settings
from app.core.exceptions import AppError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LLMResult:
    text: str
    model: str
    usage: dict[str, int]
    latency_ms: int


class LLMClient(ModelHTTPClient):
    service_label = "模型服务"

    def __init__(
        self,
        *,
        api_base: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        settings = get_settings()
        super().__init__(
            api_base=settings.llm_api_base if api_base is None else api_base,
            api_key=settings.llm_api_key if api_key is None else api_key,
            transport=transport,
        )
        self.model = settings.llm_model if model is None else model

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
        response = self._request_with_retry(
            lambda: self._client.post(
                "/chat/completions",
                json=payload,
                headers=self._headers(),
                timeout=timeout_s,
            ),
            model=model or self.model,
        )
        elapsed_ms = int((time.monotonic() - started) * 1000)
        return self._parse_result(response, model or self.model, elapsed_ms)

    def probe(self, *, timeout_s: float = 15) -> None:
        """保存配置时的连通性校验：单次请求，不重试。

        通过标准：HTTP 200 且 `choices` 非空；不要求 `content` 非空，
        以兼容思考型模型在小 `max_tokens` 下只输出思考内容的情况。
        """
        self._ensure_configured()
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": "请只回复：正常"}],
            "temperature": 0,
            "max_tokens": 32,
        }
        response = self._client.post(
            "/chat/completions",
            json=payload,
            headers=self._headers(),
            timeout=timeout_s,
        )
        if response.status_code != httpx.codes.OK:
            raise self.http_error(response)
        try:
            data = response.json()
        except ValueError:
            raise AppError(
                "MODEL_OUTPUT_INVALID",
                "模型输出无法解析",
                http_status=502,
                retryable=False,
            ) from None
        if not (data.get("choices") or []):
            raise AppError(
                "MODEL_OUTPUT_INVALID",
                "模型输出为空",
                http_status=502,
                retryable=False,
            )

    def list_models(self, *, timeout_s: float = 10) -> list[str]:
        """拉取服务商可用模型清单（OpenAI 兼容 `GET /models`），单次请求不重试。"""
        self._ensure_configured()
        host = urlsplit(self.api_base).hostname or "invalid"
        try:
            response = self._client.get("/models", headers=self._headers(), timeout=timeout_s)
        except httpx.TimeoutException:
            logger.warning("模型列表拉取超时 host=%s", host)
            raise self._timeout_error() from None
        except httpx.HTTPError:
            logger.warning("模型列表拉取网络异常 host=%s", host)
            raise self._network_error() from None
        if response.status_code != httpx.codes.OK:
            raise self.http_error(response)
        try:
            data = response.json()
        except ValueError:
            raise AppError(
                "MODEL_OUTPUT_INVALID",
                "模型列表无法解析",
                http_status=502,
                retryable=False,
            ) from None
        items = data.get("data") or []
        models: list[str] = []
        for item in items:
            if isinstance(item, dict) and item.get("id"):
                models.append(str(item["id"]))
        return sorted(models)

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
        # 解析预处理：剥离 markdown 围栏、截取括号范围，再做 schema 校验
        raw = normalize_json_text(result.text)
        try:
            return schema.model_validate_json(raw)
        except ValidationError as exc:
            raise AppError(
                "MODEL_OUTPUT_INVALID",
                "模型输出无法解析",
                http_status=502,
                retryable=False,
                # 字段路径 + 规则错误（不含模型原文），供业务层修复重试与规范日志使用
                details={"validation": validation_error_summary(exc)},
            ) from None

    def _ensure_configured(self) -> None:
        if not self.api_base or not self.api_key:
            raise AppError(
                "MODEL_CONFIG_REQUIRED",
                "未配置大模型（LLM）",
                http_status=400,
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
