from __future__ import annotations

import logging
import subprocess
from pathlib import Path

import httpx

from app.ai import audit
from app.ai.chain import configured_chain, should_fall_back
from app.ai.http_client import ModelHTTPClient
from app.ai.retry import MAX_ATTEMPTS, RetryPolicy
from app.core import metrics
from app.core.config import get_settings
from app.core.exceptions import AppError

logger = logging.getLogger(__name__)

_MIME_TYPES = {
    "mp3": "audio/mpeg",
    "wav": "audio/wav",
    "m4a": "audio/mp4",
    "webm": "audio/webm",
}

# Chromium/Firefox MediaRecorder 产出的容器格式（Opus 编码），FunASR 无法解码
# （返回空文本），送 ASR 前必须用 ffmpeg 转为 16k 单声道 wav。
_TRANSCODE_EXTENSIONS = {"webm", "ogg", "oga", "opus"}

# 时长探测超时（秒）：只读元数据，超时即放弃探测、不阻断转写
_PROBE_TIMEOUT_S = 15.0

# 审计场景名：文件转写与实时分片分开统计（见 ai-design.md 3.11）
SCENE_ASR = "asr"
SCENE_ASR_LIVE = "asr_live"


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


def probe_duration_seconds(content: bytes, file_name: str) -> float | None:
    """用 ffprobe 读取音频时长（秒），供发送前预检。

    - ffprobe 未安装或探测失败返回 `None`（不阻断，回退到只按体积预检）；
    - 只读元数据，不落盘，超时 `PROBE_TIMEOUT_S` 秒即放弃。
    """
    try:
        proc = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                "-i", "pipe:0",
            ],
            input=content,
            capture_output=True,
            timeout=_PROBE_TIMEOUT_S,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    raw = proc.stdout.decode(errors="replace").strip().splitlines()
    if not raw:
        return None
    try:
        return float(raw[0])
    except ValueError:
        return None


class TranscriptionClient(ModelHTTPClient):
    service_label = "音频转写"
    # 转写非幂等：读超时可能已被 ASR 计费并返回结果，不重传
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
            api_base=settings.asr_api_base if api_base is None else api_base,
            api_key=settings.asr_api_key if api_key is None else api_key,
            transport=transport,
            # 全局 deadline：含重试与退避的总预算，防止单次调用无限膨胀（<=0 关闭）
            retry_policy=RetryPolicy(
                max_attempts=MAX_ATTEMPTS,
                deadline_s=(
                    settings.asr_call_deadline_s
                    if settings.asr_call_deadline_s > 0
                    else None
                ),
                retry_ambiguous=False,
            ),
        )
        self.model = settings.asr_model if model is None else model

    def transcribe(self, content: bytes, file_name: str) -> str:
        """转写一段音频；`ASR_FALLBACK_MODELS` 配置时按序切换同 provider 备用模型。"""
        self._ensure_configured()
        extension = Path(file_name).suffix.lower().lstrip(".")
        if extension in _TRANSCODE_EXTENSIONS:
            content, file_name, mime_type = transcode_to_wav(content, file_name)
        else:
            mime_type = _MIME_TYPES.get(extension, "application/octet-stream")
        settings = get_settings()
        timeout_s = settings.asr_timeout_s
        chain = configured_chain(self.model, settings.asr_fallback_models)
        last_error: AppError | None = None
        for index, candidate in enumerate(chain):
            try:
                response = self._request_with_retry(
                    # 默认参数绑定本轮模型，规避 B023 循环变量捕获
                    lambda attempt_timeout, _model=candidate: self._client.post(
                        "/audio/transcriptions",
                        data={"model": _model},
                        files={"file": (file_name, content, mime_type)},
                        headers={"Authorization": f"Bearer {self.api_key}"},
                        timeout=attempt_timeout,
                    ),
                    model=candidate,
                    timeout_s=timeout_s,
                )
            except AppError as exc:
                last_error = exc
                if index + 1 < len(chain) and should_fall_back(exc):
                    metrics.inc_counter("ai_fallback_total")
                    audit.note_fallback(candidate, scene=SCENE_ASR)
                    logger.warning(
                        "ASR 降级切换 model=%s → %s error_code=%s",
                        candidate,
                        chain[index + 1],
                        exc.error_code,
                    )
                    continue
                raise
            return self._parse_text(response, candidate)
        raise last_error or self._network_error()

    def _ensure_configured(self) -> None:
        if not self.api_base or not self.api_key or not self.model:
            raise AppError(
                "MODEL_CONFIG_REQUIRED",
                "未配置音频转写服务，请设置 ASR_API_BASE / ASR_API_KEY / ASR_MODEL",
                http_status=400,
            )

    def _parse_text(self, response: httpx.Response, model: str | None = None) -> str:
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
        if model:
            logger.info("ASR 调用成功 model=%s chars=%d", model, len(text))
        return text.strip()


__all__ = [
    "SCENE_ASR",
    "SCENE_ASR_LIVE",
    "TranscriptionClient",
    "probe_duration_seconds",
    "transcode_to_wav",
]
