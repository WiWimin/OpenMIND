"""LLM 模型降级链（`ai-design.md 3.9`）：读取 `LLM_FALLBACK_MODELS` 的薄封装。

链的通用实现见 `app/ai/chain.py`；本模块保留 `app.ai.llm.chain` 的公开符号，
`LLMClient` 经此读取 `LLM_FALLBACK_MODELS` 构造候选链。
"""

from __future__ import annotations

from app.ai.chain import (
    FALLBACK_ERROR_CODES,
    MAX_CHAIN_LENGTH,
    build_chain,
    parse_fallback_models,
    should_fall_back,
)
from app.core.config import get_settings

__all__ = [
    "FALLBACK_ERROR_CODES",
    "MAX_CHAIN_LENGTH",
    "build_chain",
    "configured_chain",
    "parse_fallback_models",
    "should_fall_back",
]


def configured_chain(primary: str | None) -> list[str]:
    """读取 `LLM_FALLBACK_MODELS` 构造当前生效的候选链。"""
    return build_chain(primary, parse_fallback_models(get_settings().llm_fallback_models))
