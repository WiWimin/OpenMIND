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
    deltas: tuple[str | tuple[str, str], ...] | list[str],
    *,
    usage: tuple[int, int] | None = None,
    model: str = "fake-model",
) -> str:
    """构造 OpenAI 风格的 SSE 响应体（`data:` 行 + `[DONE]`）。

    增量元素可以是正文字符串，或 `(delta 字段名, 文本)` 元组
    （如 `("reasoning_content", "先想想")`）。
    """
    events: list[str] = []
    for item in deltas:
        delta: dict
        if isinstance(item, tuple):
            delta = {item[0]: item[1]}
        else:
            delta = {"content": item}
        events.append(
            "data: "
            + json.dumps(
                {"model": model, "choices": [{"delta": delta}]},
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


def _collect_events(client: LLMClient) -> list[tuple[str, str]]:
    """用 `astream_chat_events` 收集 `(kind, text)` 增量。"""

    async def run() -> list[tuple[str, str]]:
        return [
            (chunk.kind, chunk.text)
            async for chunk in client.astream_chat_events(
                [{"role": "user", "content": "问题"}]
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
        assert body["stream_options"] == {"include_usage": True}
        return httpx.Response(
            200, text=_sse_body(("你", "好"), usage=(123, 45))
        )

    client = _client(handler, monkeypatch)
    usage: list[dict[str, int]] = []
    deltas = _collect(client, usage)

    assert deltas == ["你", "好"]
    assert calls["n"] == 1
    assert usage and usage[-1] == {"input": 123, "output": 45}


def test_astream_omits_stream_options_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """兼容层不认 stream_options 时可关闭（用量审计会退回 0）。"""
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "ai_stream_include_usage", False)
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content))
        return httpx.Response(200, text=_sse_body(("好",)))

    _collect(_client(handler, monkeypatch))

    assert "stream_options" not in seen


def test_astream_without_usage_chunk_never_calls_on_usage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """真实 provider 默认不回 usage：此时 on_usage 一次都不应触发。"""
    usage: list[dict[str, int]] = []
    client = _client(
        lambda _: httpx.Response(200, text=_sse_body(("你", "好"))), monkeypatch
    )

    assert _collect(client, usage) == ["你", "好"]
    assert usage == []


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


# ============================ 思考过程（推理链） ============================


def test_astream_events_yields_reasoning_before_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """reasoning_content 先于正文下发，顺序与服务商一致。"""
    client = _client(
        lambda _: httpx.Response(
            200, text=_sse_body((("reasoning_content", "先想想"), "答案"))
        ),
        monkeypatch,
    )

    assert _collect_events(client) == [
        ("reasoning", "先想想"),
        ("content", "答案"),
    ]


def test_astream_events_parses_reasoning_aliases(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OpenRouter 风格的 `reasoning` / `reasoning_details` 同样识别。"""
    client = _client(
        lambda _: httpx.Response(
            200,
            text=_sse_body(
                (
                    ("reasoning", "别名推理"),
                    ("reasoning_details", [{"text": "细节"}]),
                    "好",
                )
            ),
        ),
        monkeypatch,
    )

    assert _collect_events(client) == [
        ("reasoning", "别名推理"),
        ("reasoning", "细节"),
        ("content", "好"),
    ]


def test_astream_chat_wrapper_drops_reasoning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """兼容包装只返回正文：老调用方行为不变。"""
    client = _client(
        lambda _: httpx.Response(
            200, text=_sse_body((("reasoning_content", "思考"), "答案"))
        ),
        monkeypatch,
    )

    assert _collect(client) == ["答案"]


def test_thinking_payload_sent_only_for_thinking_models(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GLM-4.5+ 注入 thinking 开关；老模型不注入未知字段（避免兼容层 400）。"""
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.clear()
        seen.update(json.loads(request.content))
        return httpx.Response(200, text=_sse_body(("好",)))

    transport = httpx.MockTransport(handler)
    zhipu = LLMClient(
        api_base="https://open.bigmodel.cn/api/paas/v4",
        api_key="sk-test",
        model="glm-4.6",
        transport=transport,
    )
    _collect_events(zhipu)
    assert seen["thinking"] == {"type": "enabled"}

    flash = LLMClient(
        api_base="https://open.bigmodel.cn/api/paas/v4",
        api_key="sk-test",
        model="glm-4-flash",
        transport=transport,
    )
    _collect_events(flash)
    assert "thinking" not in seen


def test_thinking_off_disables_thinking_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """关闭思考开关：对可开关模型发送 disabled。"""
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.clear()
        seen.update(json.loads(request.content))
        return httpx.Response(200, text=_sse_body(("好",)))

    client = LLMClient(
        api_base="https://open.bigmodel.cn/api/paas/v4",
        api_key="sk-test",
        model="glm-4.6",
        transport=httpx.MockTransport(handler),
    )

    async def run() -> list[str]:
        return [
            chunk.text
            async for chunk in client.astream_chat_events(
                [{"role": "user", "content": "问题"}], thinking=False
            )
        ]

    asyncio.run(run())
    assert seen["thinking"] == {"type": "disabled"}


def test_reasoning_capped_by_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """推理文本按 `AI_REASONING_MAX_CHARS` 截断并附提示，正文不受影响。"""
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "ai_reasoning_max_chars", 5)
    client = _client(
        lambda _: httpx.Response(
            200,
            text=_sse_body(
                (("reasoning_content", "一二三四五六七八九十"), "答案")
            ),
        ),
        monkeypatch,
    )

    events = _collect_events(client)
    reasoning = "".join(text for kind, text in events if kind == "reasoning")
    assert "一二三四五" in reasoning
    assert "截断" in reasoning
    assert ("content", "答案") in events


def test_reasoning_only_stream_raises_and_does_not_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """只收到推理、没有正文：判空输出，且已下发推理后不再重试。"""
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(
            200, text=_sse_body((("reasoning_content", "只有思考"),))
        )

    client = _client(handler, monkeypatch)

    with pytest.raises(AppError) as exc_info:
        _collect_events(client)

    assert exc_info.value.error_code == "MODEL_OUTPUT_INVALID"
    assert calls["n"] == 1
