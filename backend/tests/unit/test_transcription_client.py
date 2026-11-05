import httpx
import pytest

from app.ai.transcription import TranscriptionClient
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
