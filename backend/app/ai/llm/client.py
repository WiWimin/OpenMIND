from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, ValidationError

from app.ai import connection, resilience
from app.ai.http_client import (
    BACKOFF_SECONDS,
    ModelHTTPClient,
    app_error_kind,
    classify_transport_error,
    log_transport_warning,
)
from app.ai.retry import MAX_ATTEMPTS, RetryPolicy
from app.ai.structured import normalize_json_text, validation_error_summary
from app.core import metrics
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
    # chat 补全非幂等：读超时/传输中断可能已被服务商计费，不重传
    idempotent = False

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
            # 全局 deadline：含重试与退避的总预算，防止单次调用穿透网关超时（<=0 关闭）
            retry_policy=RetryPolicy(
                max_attempts=MAX_ATTEMPTS,
                deadline_s=(
                    settings.ai_call_deadline_s if settings.ai_call_deadline_s > 0 else None
                ),
                retry_ambiguous=False,
            ),
        )
        # 异步流式请求复用同一 transport（测试注入 MockTransport）
        self._transport = transport
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
            lambda attempt_timeout: self._client.post(
                "/chat/completions",
                json=payload,
                headers=self._headers(),
                timeout=attempt_timeout,
            ),
            model=model or self.model,
            timeout_s=timeout_s,
        )
        elapsed_ms = int((time.monotonic() - started) * 1000)
        return self._parse_result(response, model or self.model, elapsed_ms)

    async def astream_chat(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        timeout_s: float = 60,
        on_usage: Callable[[dict[str, int]], None] | None = None,
    ) -> AsyncIterator[str]:
        """流式对话（SSE）：逐段 yield `choices[0].delta.content`。

        - **首个增量前**允许 1 次退避重试，但按幂等性分级：`429/5xx/连接失败`
          可重试，`读超时/传输中断`（请求可能已被计费）**不重传**；
        - **首增量后一律不重试**（已下发部分答案，重试会造成重复内容）；
        - 非 200 先读响应体再按统一错误映射；收到 `[DONE]` 结束；
        - 无增量且无异常 → `MODEL_OUTPUT_INVALID`；
        - `on_usage` 在收到 usage 分片时回调（终态分片可能无内容增量）。
        """
        self._ensure_configured()
        resolved_model = model or self.model
        payload: dict[str, Any] = {
            "model": resolved_model,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        emitted = False
        last_error: AppError | None = None
        for attempt in range(2):
            if attempt:
                metrics.inc_counter("ai_retry_total")
                await asyncio.sleep(BACKOFF_SECONDS[attempt - 1])
            try:
                async for delta in self._stream_once(
                    payload, resolved_model, timeout_s, on_usage=on_usage
                ):
                    emitted = True
                    yield delta
            except AppError as exc:
                last_error = exc
                if emitted or not self.retry_policy.allows(
                    app_error_kind(exc), retryable=exc.retryable
                ):
                    raise
            except httpx.TimeoutException as exc:
                kind = classify_transport_error(exc)
                log_transport_warning(
                    f"{self.service_label}超时", self.api_base, resolved_model, exc
                )
                last_error = self._timeout_error()
                if emitted or not self.retry_policy.allows(kind, retryable=True):
                    raise last_error from None
            except httpx.HTTPError as exc:
                kind = classify_transport_error(exc)
                log_transport_warning(
                    f"{self.service_label}网络异常", self.api_base, resolved_model, exc
                )
                last_error = self._network_error()
                if emitted or not self.retry_policy.allows(kind, retryable=True):
                    raise last_error from None
            else:
                if emitted:
                    logger.info("LLM 流式调用成功 model=%s", resolved_model)
                    return
                last_error = AppError(
                    "MODEL_OUTPUT_INVALID",
                    "模型输出为空",
                    http_status=502,
                    retryable=False,
                )
                raise last_error
        raise last_error or self._network_error()

    async def _stream_once(
        self,
        payload: dict[str, Any],
        model: str,
        timeout_s: float,
        *,
        on_usage: Callable[[dict[str, int]], None] | None,
    ) -> AsyncIterator[str]:
        """单次流式请求：解析 SSE `data:` 行并 yield 内容增量。

        客户端来自 `app/ai/connection.py` 的异步池（按事件循环 + api_base 复用），
        注入 transport（测试）时按次新建并随 `async with` 关闭。
        """
        client = connection.get_async_client(self.api_base, transport=self._transport)
        if connection.pooled(self._transport):
            async for delta in self._iter_stream(
                client, payload, model, timeout_s, on_usage=on_usage
            ):
                yield delta
            return
        async with client:
            async for delta in self._iter_stream(
                client, payload, model, timeout_s, on_usage=on_usage
            ):
                yield delta

    async def _iter_stream(
        self,
        client: httpx.AsyncClient,
        payload: dict[str, Any],
        model: str,
        timeout_s: float,
        *,
        on_usage: Callable[[dict[str, int]], None] | None,
    ) -> AsyncIterator[str]:
        """单次流请求体：非 200 先读响应体再按统一错误映射。

        与同步路径共用并发闸门与熔断（`app/ai/resilience.py`）：
        发包前 `breaker.check` + `gate.aacquire`，正常结束记成功，
        5xx/超时/传输中断记失败；消费者提前关闭（GeneratorExit，如前端断开）
        只释放名额、不计入熔断失败。
        """
        gate = resilience.get_gate()
        breaker = resilience.get_breaker()
        gkey = resilience.gate_key(self.api_base)
        bkey = resilience.breaker_key(self.api_base, model)

        try:
            breaker.check(bkey)
        except AppError:
            metrics.inc_counter("ai_circuit_open_total")
            raise
        if not await gate.aacquire(
            gkey, timeout_s=get_settings().ai_concurrency_timeout_s
        ):
            metrics.inc_counter("ai_concurrency_rejected_total")
            raise AppError(
                "RATE_LIMITED",
                f"{self.service_label}并发已满，请稍后重试",
                http_status=429,
                retryable=True,
                details={"scope": "concurrency"},
            )
        completed = False
        try:
            async with client.stream(
                "POST",
                "/chat/completions",
                json=payload,
                headers=self._headers(),
                timeout=timeout_s,
            ) as response:
                if response.status_code != httpx.codes.OK:
                    # 非 200 需先读响应体才能映射额度类错误
                    await response.aread()
                    if 500 <= response.status_code < 600:
                        breaker.record_failure(bkey)
                    raise self.http_error(response)
                async for line in response.aiter_lines():
                    stripped = line.strip()
                    if not stripped.startswith("data:"):
                        continue
                    data = stripped[5:].strip()
                    if data == "[DONE]":
                        completed = True
                        return
                    try:
                        chunk = json.loads(data)
                    except ValueError:
                        logger.debug("流式分片无法解析，已忽略 model=%s", model)
                        continue
                    if not isinstance(chunk, dict):
                        continue
                    usage = chunk.get("usage")
                    if usage and on_usage:
                        on_usage(
                            {
                                "input": int(usage.get("prompt_tokens") or 0),
                                "output": int(usage.get("completion_tokens") or 0),
                            }
                        )
                    choices = chunk.get("choices") or []
                    if not choices:
                        continue
                    delta = (choices[0].get("delta") or {}).get("content")
                    if delta:
                        yield delta
                # 流正常读完但未见 [DONE]：同样视为 provider 正常响应
                completed = True
        except GeneratorExit:
            # 消费者提前关闭（前端断开/上层取消）：不判定为 provider 失败
            raise
        except httpx.TimeoutException:
            breaker.record_failure(bkey)
            raise
        except httpx.HTTPError:
            breaker.record_failure(bkey)
            raise
        finally:
            # `return`（收到 [DONE]）会跳过 else，故成功判定放在 finally 内
            if completed:
                breaker.record_success(bkey)
            gate.release(gkey)

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
