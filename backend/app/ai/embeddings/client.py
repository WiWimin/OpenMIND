from __future__ import annotations

import logging
import time

import httpx

from app.core.config import get_settings
from app.core.exceptions import AppError

logger = logging.getLogger(__name__)

_BACKOFF_SECONDS = (1, 3)
_MAX_ATTEMPTS = 3
_MAX_BATCH_SIZE = 16
_BATCH_TIMEOUT_S = 30.0


class EmbeddingClient:
    def __init__(
        self,
        *,
        api_base: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        transport: httpx.BaseTransport | None = None,
        batch_size: int = _MAX_BATCH_SIZE,
        dim: int | None = None,
    ) -> None:
        settings = get_settings()
        self.api_base = (api_base or settings.embedding_api_base).rstrip("/")
        self.api_key = api_key or settings.embedding_api_key
        self.model = model or settings.embedding_model
        self.dim = dim if dim is not None else settings.embedding_dim
        self.batch_size = min(batch_size, _MAX_BATCH_SIZE)
        self._client = httpx.Client(base_url=self.api_base, transport=transport)

    def embed(self, texts: list[str], *, model: str | None = None) -> list[list[float]]:
        self._ensure_configured()
        if not texts:
            return []
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            batch = texts[start : start + self.batch_size]
            vectors.extend(self._embed_batch(batch, model=model))
        return vectors

    def _embed_batch(self, texts: list[str], *, model: str | None) -> list[list[float]]:
        payload = {"model": model or self.model, "input": list(texts)}
        last_error: AppError | None = None
        for attempt in range(_MAX_ATTEMPTS):
            if attempt:
                time.sleep(_BACKOFF_SECONDS[attempt - 1])
            try:
                response = self._client.post(
                    "/embeddings",
                    json=payload,
                    headers=self._headers(),
                    timeout=_BATCH_TIMEOUT_S,
                )
            except httpx.TimeoutException:
                last_error = AppError(
                    "MODEL_TIMEOUT", "向量服务超时", http_status=504, retryable=True
                )
            except httpx.HTTPError:
                last_error = AppError(
                    "INTERNAL_ERROR",
                    "向量服务网络异常",
                    http_status=500,
                    retryable=True,
                )
            else:
                if response.status_code == httpx.codes.OK:
                    return self._parse_embeddings(response, len(texts))
                last_error = self._http_error(response)
            if not last_error.retryable:
                raise last_error
        raise last_error or AppError(
            "INTERNAL_ERROR", "向量服务异常", http_status=500, retryable=True
        )

    def _ensure_configured(self) -> None:
        if not self.api_base or not self.api_key:
            raise AppError("INTERNAL_ERROR", "向量服务未配置", http_status=500, retryable=False)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _http_error(self, response: httpx.Response) -> AppError:
        status_code = response.status_code
        if status_code == 429:
            return AppError("RATE_LIMITED", "向量服务限流", http_status=429, retryable=True)
        if 500 <= status_code < 600:
            return AppError("INTERNAL_ERROR", "向量服务异常", http_status=500, retryable=True)
        return AppError("INTERNAL_ERROR", "向量服务调用失败", http_status=500, retryable=False)

    def _parse_embeddings(self, response: httpx.Response, expected: int) -> list[list[float]]:
        try:
            data = response.json()
        except ValueError:
            raise AppError(
                "INTERNAL_ERROR",
                "向量服务返回异常",
                http_status=500,
                retryable=False,
            ) from None
        items = data.get("data") or []
        ordered = sorted(items, key=lambda item: item.get("index", 0))
        vectors: list[list[float]] = []
        for item in ordered:
            vector = item.get("embedding")
            if not isinstance(vector, list):
                raise AppError(
                    "INTERNAL_ERROR",
                    "向量服务返回异常",
                    http_status=500,
                    retryable=False,
                )
            floats = [float(value) for value in vector]
            if len(floats) != self.dim:
                logger.error(
                    "Embedding 维度不匹配 expected=%d got=%d",
                    self.dim,
                    len(floats),
                )
                raise AppError(
                    "INTERNAL_ERROR",
                    "向量维度不匹配",
                    http_status=500,
                    retryable=False,
                )
            vectors.append(floats)
        if len(vectors) != expected:
            raise AppError(
                "INTERNAL_ERROR",
                "向量服务返回数量异常",
                http_status=500,
                retryable=False,
            )
        logger.info("Embedding 调用成功 count=%d dim=%d", len(vectors), self.dim)
        return vectors
