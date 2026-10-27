from __future__ import annotations

import time
from pathlib import Path

import httpx

from app.core.config import get_settings
from app.core.exceptions import AppError

_BACKOFF_SECONDS = (1, 3)
_MAX_ATTEMPTS = 3

_MIME_TYPES = {
    "mp3": "audio/mpeg",
    "wav": "audio/wav",
    "m4a": "audio/mp4",
    "webm": "audio/webm",
}

_QUOTA_HINTS = ("quota", "balance", "insufficient", "billing", "免费额度", "额度", "余额")


def _is_quota_error(response: httpx.Response) -> bool:
    try:
        text = response.text.lower()
    except Exception:
        return False
    return any(hint in text for hint in _QUOTA_HINTS)


class TranscriptionClient:
    def __init__(
        self,
        *,
        api_base: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        settings = get_settings()
        self.api_base = (settings.asr_api_base if api_base is None else api_base).rstrip("/")
        self.api_key = settings.asr_api_key if api_key is None else api_key
        self.model = settings.asr_model if model is None else model
        self._client = httpx.Client(base_url=self.api_base, transport=transport)

    def transcribe(self, content: bytes, file_name: str) -> str:
        self._ensure_configured()
        extension = Path(file_name).suffix.lower().lstrip(".")
        mime_type = _MIME_TYPES.get(extension, "application/octet-stream")
        last_error: AppError | None = None
        for attempt in range(_MAX_ATTEMPTS):
            if attempt:
                time.sleep(_BACKOFF_SECONDS[attempt - 1])
            try:
                response = self._client.post(
                    "/audio/transcriptions",
                    data={"model": self.model},
                    files={"file": (file_name, content, mime_type)},
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    timeout=120,
                )
            except httpx.TimeoutException:
                last_error = AppError(
                    "MODEL_TIMEOUT", "音频转写超时", http_status=504, retryable=True
                )
            except httpx.HTTPError:
                last_error = AppError(
                    "INTERNAL_ERROR", "音频转写网络异常", http_status=500, retryable=True
                )
            else:
                if response.status_code == httpx.codes.OK:
                    return self._parse_text(response)
                last_error = self._http_error(response)
            if not last_error.retryable:
                raise last_error
        raise last_error or AppError(
            "INTERNAL_ERROR", "音频转写失败", http_status=500, retryable=True
        )

    def _ensure_configured(self) -> None:
        if not self.api_base or not self.api_key or not self.model:
            raise AppError(
                "MODEL_CONFIG_REQUIRED",
                "未配置音频转写服务，请设置 ASR_API_BASE / ASR_API_KEY / ASR_MODEL",
                http_status=400,
            )

    def _parse_text(self, response: httpx.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            raise AppError(
                "MODEL_OUTPUT_INVALID",
                "音频转写返回格式无效",
                http_status=502,
            ) from None
        text = payload.get("text") if isinstance(payload, dict) else None
        if not isinstance(text, str) or not text.strip():
            raise AppError(
                "MODEL_OUTPUT_INVALID",
                "音频转写没有返回文本",
                http_status=502,
            )
        return text.strip()

    def _http_error(self, response: httpx.Response) -> AppError:
        if response.status_code == httpx.codes.PAYMENT_REQUIRED or _is_quota_error(response):
            return AppError(
                "MODEL_QUOTA_EXCEEDED",
                "音频转写额度不足",
                http_status=402,
                retryable=False,
            )
        if response.status_code == httpx.codes.TOO_MANY_REQUESTS:
            return AppError(
                "RATE_LIMITED", "音频转写服务限流", http_status=429, retryable=True
            )
        if response.status_code in {httpx.codes.UNAUTHORIZED, httpx.codes.FORBIDDEN}:
            return AppError(
                "MODEL_CONFIG_INVALID",
                "音频转写密钥无效",
                http_status=400,
                retryable=False,
            )
        if 400 <= response.status_code < 500:
            return AppError(
                "MODEL_CONFIG_INVALID",
                "音频转写请求无效",
                http_status=400,
                retryable=False,
            )
        return AppError(
            "INTERNAL_ERROR", "音频转写服务异常", http_status=500, retryable=True
        )
