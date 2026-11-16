"""思考模式（推理链）：模型能力识别、请求参数与 reasoning 字段解析。"""

from __future__ import annotations

from app.ai.llm.reasoning import (
    extract_reasoning,
    reasoning_capable,
    thinking_payload,
)


def test_thinking_payload_for_zhipu_thinking_models() -> None:
    assert thinking_payload("glm-4.6", "https://open.bigmodel.cn/v4", True) == {
        "thinking": {"type": "enabled"}
    }
    assert thinking_payload("glm-4.5-air", "https://open.bigmodel.cn/v4", False) == {
        "thinking": {"type": "disabled"}
    }


def test_thinking_payload_skips_legacy_models() -> None:
    """老模型不注入未知字段，避免兼容层 400。"""
    assert thinking_payload("glm-4-flash", "https://open.bigmodel.cn/v4", True) == {}
    assert thinking_payload("gpt-4o-mini", "https://api.openai.com/v1", True) == {}


def test_thinking_payload_for_qwen3_on_supported_hosts() -> None:
    assert thinking_payload(
        "qwen3-32b", "https://dashscope.aliyuncs.com/compatible-mode/v1", True
    ) == {"enable_thinking": True}
    # 非 DashScope/SiliconFlow 的同名模型不注入
    assert thinking_payload("qwen3-32b", "https://proxy.example.com/v1", True) == {}


def test_reasoning_capable() -> None:
    assert reasoning_capable("deepseek-reasoner", "https://api.deepseek.com") is True
    assert reasoning_capable("glm-4.6", "https://open.bigmodel.cn/v4") is True
    assert reasoning_capable("glm-4-flash", "https://open.bigmodel.cn/v4") is False
    assert reasoning_capable("", "https://api.example.com") is False


def test_extract_reasoning_shapes() -> None:
    assert extract_reasoning({"reasoning_content": "想一想"}) == "想一想"
    assert extract_reasoning({"reasoning": "想一想"}) == "想一想"
    assert extract_reasoning({"reasoning_details": [{"text": "细节"}]}) == "细节"
    assert extract_reasoning({"reasoning": {"content": "嵌套"}}) == "嵌套"
    assert extract_reasoning({"content": "正文"}) == ""
