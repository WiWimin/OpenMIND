from __future__ import annotations

from pathlib import Path

import httpx

from app.ai.http_client import ModelHTTPClient
from app.core.config import get_settings
from app.core.exceptions import AppError

_MIME_TYPES = {
    "mp3": "audio/mpeg",
    "wav": "audio/wav",
    "m4a": "audio/mp4",
    "webm": "audio/webm",
}


class TranscriptionClient(ModelHTTPClient):
    service_label = "音频转写"

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
            api_base=settings.asr_api_base if api_base is None else api_base,
            api_key=settings.asr_api_key if api_key is None else api_key,
            transport=transport,
        )
        self.model = settings.asr_model if model is None else model

    def transcribe(self, content: bytes, file_name: str) -> str:
        self._ensure_configured()
        extension = Path(file_name).suffix.lower().lstrip(".")
        mime_type = _MIME_TYPES.get(extension, "application/octet-stream")
        response = self._request_with_retry(
            lambda: self._client.post(
                "/audio/transcriptions",
                data={"model": self.model},
                files={"file": (file_name, content, mime_type)},
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=120,
            ),
            model=self.model,
        )
        return self._parse_text(response)

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
