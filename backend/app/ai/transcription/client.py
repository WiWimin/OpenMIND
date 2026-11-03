from __future__ import annotations

import subprocess
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

# Chromium/Firefox MediaRecorder 产出的容器格式（Opus 编码），FunASR 无法解码
# （返回空文本），送 ASR 前必须用 ffmpeg 转为 16k 单声道 wav。
_TRANSCODE_EXTENSIONS = {"webm", "ogg", "oga", "opus"}


def transcode_to_wav(content: bytes, file_name: str) -> tuple[bytes, str, str]:
    """把 webm/ogg 音频经 ffmpeg 转为 16kHz 单声道 wav。

    返回 (wav_bytes, 新文件名, mime)；ffmpeg 缺失/失败时抛 FILE_PARSE_FAILED。
    """
    try:
        proc = subprocess.run(
            [
                "ffmpeg", "-v", "error", "-i", "pipe:0",
                "-f", "wav", "-ar", "16000", "-ac", "1", "pipe:1",
            ],
            input=content,
            capture_output=True,
            timeout=60,
        )
    except FileNotFoundError:
        raise AppError(
            "FILE_PARSE_FAILED",
            "服务器未安装 ffmpeg，无法转码 webm/ogg 音频",
            http_status=500,
            retryable=False,
        ) from None
    except subprocess.TimeoutExpired:
        raise AppError(
            "FILE_PARSE_FAILED",
            "音频转码超时",
            http_status=500,
            retryable=False,
        ) from None
    if proc.returncode != 0 or not proc.stdout:
        detail = proc.stderr.decode(errors="replace").strip()[:200]
        raise AppError(
            "FILE_PARSE_FAILED",
            f"音频转码失败：{detail or 'ffmpeg 无输出'}",
            http_status=500,
            retryable=False,
        )
    return proc.stdout, f"{Path(file_name).stem}.wav", "audio/wav"


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
        if extension in _TRANSCODE_EXTENSIONS:
            content, file_name, mime_type = transcode_to_wav(content, file_name)
        else:
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
