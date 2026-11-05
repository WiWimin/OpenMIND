from __future__ import annotations

import logging

import httpx

from app.ai.http_client import ModelHTTPClient
from app.core.config import get_settings
from app.core.exceptions import AppError

logger = logging.getLogger(__name__)

_MAX_BATCH_SIZE = 16
_BATCH_TIMEOUT_S = 30.0


class EmbeddingClient(ModelHTTPClient):
    service_label = "向量服务"

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
        super().__init__(
            api_base=settings.embedding_api_base if api_base is None else api_base,
            api_key=settings.embedding_api_key if api_key is None else api_key,
            transport=transport,
        )
        self.model = settings.embedding_model if model is None else model
        self.dim = dim if dim is not None else settings.embedding_dim
        self.batch_size = min(batch_size, _MAX_BATCH_SIZE)

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
        payload = {
            "model": model or self.model,
            "input": list(texts),
            "dimensions": self.dim,
        }
        response = self._request_with_retry(
            lambda: self._client.post(
                "/embeddings",
                json=payload,
                headers=self._headers(),
                timeout=_BATCH_TIMEOUT_S,
            ),
            model=model or self.model,
        )
        return self._parse_embeddings(response, len(texts))

    def _ensure_configured(self) -> None:
        if not self.api_base or not self.api_key:
            raise AppError(
                "MODEL_CONFIG_REQUIRED",
                "服务端未配置向量模型，请联系管理员",
                http_status=400,
                retryable=False,
            )

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
