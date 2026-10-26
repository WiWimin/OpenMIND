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
