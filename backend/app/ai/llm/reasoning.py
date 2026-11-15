"""思考模式（推理链）参数与 reasoning 增量解析。

不同服务商对「思考模式」与推理文本的字段命名不一致：

- 智谱 GLM-4.5/4.6：请求 `thinking: {"type": "enabled"|"disabled"}`，
  流式增量在 `delta.reasoning_content`；
- DeepSeek Reasoner：模型本身输出 `delta.reasoning_content`，无需开关；
- Qwen3（DashScope/SiliconFlow）：`enable_thinking`；
- OpenRouter 等：`delta.reasoning` / `delta.reasoning_details`。

只对已识别的模型发送思考开关，未知兼容层不注入未知字段（避免 400）。
"""

from __future__ import annotations

import re
from typing import Any

# 智谱思考模型：只匹配 4.5+ 与 z1/z2 系列，老模型（glm-4-flash 等）不注入
_ZHIPU_THINKING = re.compile(r"^glm-(4\.5|4\.6|z1|z2)", re.IGNORECASE)
# DashScope / SiliconFlow 的 Qwen3 系列
_QWEN_THINKING = re.compile(r"^qwen3", re.IGNORECASE)
# 服务端已自动输出推理的模型
_REASONER = re.compile(r"(reasoner|thinking)", re.IGNORECASE)


def thinking_payload(model: str, api_base: str, enabled: bool) -> dict[str, Any]:
    """按模型与服务商返回思考开关请求体；未识别时返回空字典。

    只在需要时发送：`enabled=True` 才发送开启字段；关闭时仅对已识别的
    「可开关」模型发送关闭字段（省 token），其余模型不发未知字段。
    """
    name = (model or "").strip()
    host = (api_base or "").lower()
    if not name:
        return {}
    if _ZHIPU_THINKING.search(name):
        return {"thinking": {"type": "enabled" if enabled else "disabled"}}
    if _QWEN_THINKING.search(name) and any(
        marker in host for marker in ("dashscope", "siliconflow")
    ):
        return {"enable_thinking": enabled}
    if not enabled:
        return {}
    # DeepSeek Reasoner 等本身即输出推理；OpenRouter 由其模型标签控制
    return {}


def reasoning_capable(model: str, api_base: str) -> bool:
    """服务端判断该模型是否会返回原生推理（仅用于前端提示，非承诺）。"""
    if not model:
        return False
    if _REASONER.search(model):
        return True
    return bool(thinking_payload(model, api_base, True))


def _reasoning_text(value: Any) -> str:
    """把 reasoning 字段的多种形态归一为文本。

    支持：`str`、`[{"text": ...}, ...]`、`{"content"/"text": ...}`。
    """
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            parts.append(_reasoning_text(item))
        return "".join(parts)
    if isinstance(value, dict):
        for key in ("text", "content"):
            nested = value.get(key)
            if isinstance(nested, str):
                return nested
    return ""


def extract_reasoning(delta: dict[str, Any]) -> str:
    """从流式 delta 中提取推理文本（`reasoning_content` / `reasoning` / details）。"""
    parts: list[str] = []
    for key in ("reasoning_content", "reasoning", "reasoning_details"):
        text = _reasoning_text(delta.get(key))
        if text:
            parts.append(text)
    return "".join(parts)
