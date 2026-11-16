import httpx
import pytest

from app.ai.transcription import TranscriptionClient
from app.ai.transcription.client import probe_duration_seconds
from app.core import metrics
from app.core.exceptions import AppError


def test_transcription_client_parses_text() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/audio/transcriptions"
        assert request.headers["authorization"] == "Bearer test-key"
        return httpx.Response(200, json={"text": " 转写内容 "})

    client = TranscriptionClient(
        api_base="https://asr.example.com/v1",
        api_key="test-key",
        model="whisper-1",
        transport=httpx.MockTransport(handler),
    )

    assert client.transcribe(b"audio", "meeting.mp3") == "转写内容"


def test_transcription_client_requires_config() -> None:
    client = TranscriptionClient(api_base="", api_key="", model="")

    with pytest.raises(AppError) as exc_info:
        client.transcribe(b"audio", "meeting.mp3")

    assert exc_info.value.error_code == "MODEL_CONFIG_REQUIRED"


def test_transcription_client_rejects_invalid_output() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"result": "missing text"})

    client = TranscriptionClient(
        api_base="https://asr.example.com/v1",
        api_key="test-key",
        model="whisper-1",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(AppError) as exc_info:
        client.transcribe(b"audio", "meeting.mp3")

    assert exc_info.value.error_code == "MODEL_OUTPUT_INVALID"


def _client(handler) -> TranscriptionClient:
    return TranscriptionClient(
        api_base="https://asr.example.com/v1",
        api_key="test-key",
        model="sensevoice",
        transport=httpx.MockTransport(handler),
    )


def test_webm_is_transcoded_to_wav_before_send(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Chromium 录制的 webm 必须先经 ffmpeg 转码为 wav 再送 ASR。"""
    captured: dict[str, bytes] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.content
        return httpx.Response(200, json={"text": "转写内容"})

    class _Proc:
        returncode = 0
        stdout = b"RIFF-fake-wav-bytes"
        stderr = b""

    calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return _Proc()

    monkeypatch.setattr("app.ai.transcription.client.subprocess.run", fake_run)

    assert _client(handler).transcribe(b"fake-webm-data", "recording.webm") == "转写内容"
    assert len(calls) == 1
    assert calls[0][0] == "ffmpeg"
    # multipart 中应是转码后的 wav 字节与改名后的 .wav 文件名
    assert b"RIFF-fake-wav-bytes" in captured["body"]
    assert b"recording.wav" in captured["body"]


def test_webm_transcode_missing_ffmpeg(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(*args, **kwargs):
        raise FileNotFoundError("ffmpeg")

    monkeypatch.setattr("app.ai.transcription.client.subprocess.run", fake_run)

    with pytest.raises(AppError) as exc_info:
        _client(lambda _: httpx.Response(200, json={"text": "x"})).transcribe(
            b"fake-webm", "recording.webm"
        )

    assert exc_info.value.error_code == "FILE_PARSE_FAILED"
    assert "ffmpeg" in exc_info.value.message


def test_webm_transcode_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Proc:
        returncode = 1
        stdout = b""
        stderr = b"invalid data"

    monkeypatch.setattr(
        "app.ai.transcription.client.subprocess.run", lambda *a, **k: _Proc()
    )

    with pytest.raises(AppError) as exc_info:
        _client(lambda _: httpx.Response(200, json={"text": "x"})).transcribe(
            b"fake-webm", "recording.webm"
        )

    assert exc_info.value.error_code == "FILE_PARSE_FAILED"
    assert "invalid data" in exc_info.value.message


# ------------------- 场景参数：超时与全局 deadline（P0） -------------------


def test_transcription_uses_configured_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "asr_timeout_s", 7.5)
    captured: dict = {}
    client = _client(lambda _: httpx.Response(200, json={"text": "ok"}))
    original = client._request_with_retry

    def spy(send, **kwargs):  # noqa: ANN001, ANN003
        captured.update(kwargs)
        return original(send, **kwargs)

    client._request_with_retry = spy  # type: ignore[method-assign]

    assert client.transcribe(b"audio", "meeting.mp3") == "ok"
    assert captured["timeout_s"] == 7.5


def test_transcription_honours_disabled_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "asr_call_deadline_s", 0)
    client = _client(lambda _: httpx.Response(200, json={"text": "ok"}))

    assert client.retry_policy.deadline_s is None


# ------------------------- 降级链（P0） -------------------------


def test_transcription_falls_back_on_quota_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "asr_fallback_models", "backup-model")
    seen: list[bytes] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.content)
        if b"backup-model" in request.content:
            return httpx.Response(200, json={"text": "转写内容"})
        return httpx.Response(402, json={"error": {"code": "insufficient_quota"}})

    result = _client(handler).transcribe(b"audio", "meeting.mp3")

    assert result == "转写内容"
    assert len(seen) == 2
    assert metrics.snapshot()["counters"].get("ai_fallback_total") == 1


def test_transcription_no_fall_back_on_config_invalid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """密钥问题对所有模型一致，不浪费备用模型调用。"""
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "asr_fallback_models", "backup-model")
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(401, json={"error": {"message": "bad key"}})

    with pytest.raises(AppError) as exc_info:
        _client(handler).transcribe(b"audio", "meeting.mp3")

    assert exc_info.value.error_code == "MODEL_CONFIG_INVALID"
    assert len(calls) == 1


# ------------------------- 时长预检（P0） -------------------------


def test_probe_duration_parses_ffprobe_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Proc:
        returncode = 0
        stdout = b"12.5\n"
        stderr = b""

    monkeypatch.setattr(
        "app.ai.transcription.client.subprocess.run", lambda *a, **k: _Proc()
    )

    assert probe_duration_seconds(b"audio", "meeting.mp3") == 12.5


def test_probe_duration_missing_ffprobe_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom(*args, **kwargs):
        raise FileNotFoundError("ffprobe")

    monkeypatch.setattr("app.ai.transcription.client.subprocess.run", boom)

    assert probe_duration_seconds(b"audio", "meeting.mp3") is None


@pytest.mark.parametrize(
    ("returncode", "stdout"),
    [(1, b""), (0, b""), (0, b"N/A"), (0, b"")],
)
def test_probe_duration_unusable_output_returns_none(
    monkeypatch: pytest.MonkeyPatch, returncode: int, stdout: bytes
) -> None:
    class _Proc:
        pass

    proc = _Proc()
    proc.returncode = returncode
    proc.stdout = stdout
    proc.stderr = b""

    monkeypatch.setattr(
        "app.ai.transcription.client.subprocess.run", lambda *a, **k: proc
    )

    assert probe_duration_seconds(b"audio", "meeting.mp3") is None
