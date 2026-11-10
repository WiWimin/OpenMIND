"""LLM 流式调用（astream_chat）：增量解析、首增量前重试与错误映射。"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable

import httpx
import pytest

from app.ai.llm import LLMClient
from app.core.exceptions import AppError


def _sse_body(
    deltas: tuple[str, ...] | list[str],
    *,
    usage: tuple[int, int] | None = None,
    model: str = "fake-model",
) -> str:
    """构造 OpenAI 风格的 SSE 响应体（`data:` 行 + `[DONE]`）。"""
    events: list[str] = []
    for text in deltas:
        events.append(
            "data: "
            + json.dumps(
                {"model": model, "choices": [{"delta": {"content": text}}]},
                ensure_ascii=False,
            )
        )
    if usage is not None:
        events.append(
            "data: "
            + json.dumps(
                {
                    "model": model,
                    "choices": [{"delta": {}}],
                    "usage": {
                        "prompt_tokens": usage[0],
                        "completion_tokens": usage[1],
                    },
                }
            )
        )
    events.append("data: [DONE]")
    return "\n\n".join(events) + "\n\n"


def _client(
    handler: Callable[[httpx.Request], httpx.Response], monkeypatch: pytest.MonkeyPatch
) -> LLMClient:
    # 首增量前重试的退避压到 0，避免测试等待 1s
    monkeypatch.setattr("app.ai.llm.client.BACKOFF_SECONDS", (0, 0))
    return LLMClient(
        api_base="https://llm.test/v1",
        api_key="sk-test",
        model="fake-model",
        transport=httpx.MockTransport(handler),
    )


def _collect(
    client: LLMClient, on_usage: list[dict[str, int]] | None = None
) -> list[str]:
    async def run() -> list[str]:
        return [
            delta
            async for delta in client.astream_chat(
                [{"role": "user", "content": "问题"}],
                on_usage=on_usage.append if on_usage is not None else None,
            )
        ]

    return asyncio.run(run())


def test_astream_yields_deltas_and_usage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        body = json.loads(request.content)
        assert body["stream"] is True
        return httpx.Response(
            200, text=_sse_body(("你", "好"), usage=(123, 45))
        )

    client = _client(handler, monkeypatch)
    usage: list[dict[str, int]] = []
    deltas = _collect(client, usage)

    assert deltas == ["你", "好"]
    assert calls["n"] == 1
    assert usage and usage[-1] == {"input": 123, "output": 45}


def test_astream_retries_once_after_500(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(500, text="upstream boom")
        return httpx.Response(200, text=_sse_body(("恢复",)))

    client = _client(handler, monkeypatch)

    assert _collect(client) == ["恢复"]
    assert calls["n"] == 2


def test_astream_401_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(401, text="invalid api key")

    client = _client(handler, monkeypatch)

    with pytest.raises(AppError) as exc_info:
        _collect(client)

    assert exc_info.value.error_code == "MODEL_CONFIG_INVALID"
    assert calls["n"] == 1  # 不可重试错误不发起第二次请求


def test_astream_timeout_not_retried(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """首增量前的读超时不重传（非幂等，可能已计费），仅 1 次尝试。"""
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        raise httpx.ReadTimeout("read timed out")

    client = _client(handler, monkeypatch)

    with pytest.raises(AppError) as exc_info:
        _collect(client)

    assert exc_info.value.error_code == "MODEL_TIMEOUT"
    assert exc_info.value.retryable is True
    assert calls["n"] == 1


def test_astream_no_delta_raises_output_invalid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=_sse_body(()))

    client = _client(handler, monkeypatch)

    with pytest.raises(AppError) as exc_info:
        _collect(client)

    assert exc_info.value.error_code == "MODEL_OUTPUT_INVALID"


def test_astream_midstream_error_not_retried(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """首增量后断流：不重试，错误原样上抛。"""
    calls = {"n": 0}
    events = [
        "data: " + json.dumps({"choices": [{"delta": {"content": "第一段"}}]}),
        "data: " + json.dumps({"choices": [{"delta": {"content": "第二段"}}]}),
    ]

    class _BrokenStream(httpx.AsyncByteStream):
        """首个增量完整输出，随后模拟连接中断。"""

        async def __aiter__(self):
            yield (events[0] + "\n\n").encode()
            raise httpx.ReadError("connection broken")

        async def aclose(self) -> None:  # pragma: no cover — 无资源需要释放
            return None

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, stream=_BrokenStream())

    client = _client(handler, monkeypatch)

    collected: list[str] = []

    async def run() -> None:
        async for delta in client.astream_chat(
            [{"role": "user", "content": "问题"}]
        ):
            collected.append(delta)

    with pytest.raises(AppError) as exc_info:
        asyncio.run(run())

    assert collected == ["第一段"]
    assert exc_info.value.error_code == "INTERNAL_ERROR"
    assert calls["n"] == 1  # 已有增量 → 不重试
