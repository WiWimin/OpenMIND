"""输入 token 预检：发送前估算输入长度，超限直接拒绝（`ai-design.md 3.8`）。

在 `LLMClient.chat` / `astream_chat` 发包前调用，避免把明显超长的输入
打到服务商再等一次 413。估算用字符启发式（无分词器依赖）：

- CJK 统一表意文字按 1 字 ≈ 1 token（现代 BPE 对中文普遍 ≥0.8 token/字）；
- 其余字符按 4 字符 ≈ 1 token（英文/代码经验值）；
- 每条消息加 4 token 的结构开销（role/分隔符）。

估算是**下界近似**：宁可漏判（由服务商返回 `MODEL_INPUT_TOO_LONG` 兜底），
不可误杀正常输入。超限抛 `MODEL_INPUT_TOO_LONG`（413，不可重试）。
"""

from __future__ import annotations

import math
import unicodedata

from app.core.config import get_settings
from app.core.exceptions import AppError

# 每条消息的结构开销（role 标记与分隔符）
_PER_MESSAGE_OVERHEAD = 4
# 其余字符的 chars-per-token 比值
_CHARS_PER_TOKEN = 4


def _is_cjk(char: str) -> bool:
    # 统一表意文字 + 扩展 A + 兼容表意 + 假名/谚文（同属“一字一 token”量级）
    return unicodedata.name(char, "").startswith(
        ("CJK", "HIRAGANA", "KATAKANA", "HANGUL")
    )


def estimate_tokens(text: str) -> int:
    """估算单段文本的 token 数（启发式下界）。"""
    if not text:
        return 0
    cjk = sum(1 for char in text if _is_cjk(char))
    other = len(text) - cjk
    return cjk + math.ceil(other / _CHARS_PER_TOKEN)


def estimate_messages_tokens(messages: list[dict[str, str]]) -> int:
    """估算整个对话（含结构开销）的 token 数。"""
    total = 0
    for message in messages:
        content = message.get("content") or ""
        total += _PER_MESSAGE_OVERHEAD + estimate_tokens(content)
    return total


def input_limit_for(scene_limit: int | None = None) -> int:
    """生效上限：场景值 > 全局 `AI_INPUT_TOKEN_LIMIT`（<=0 表示关闭预检）。"""
    if scene_limit is not None:
        return scene_limit
    return get_settings().ai_input_token_limit


def ensure_input_within_limit(
    messages: list[dict[str, str]], *, scene_limit: int | None = None
) -> int:
    """超限时抛 `MODEL_INPUT_TOO_LONG`（413）；返回估算值供日志。"""
    limit = input_limit_for(scene_limit)
    if limit <= 0:
        return 0
    estimated = estimate_messages_tokens(messages)
    if estimated > limit:
        raise AppError(
            "MODEL_INPUT_TOO_LONG",
            "输入内容过长，超出模型处理上限",
            http_status=413,
            retryable=False,
            details={"estimated_tokens": estimated, "limit": limit},
        )
    return estimated
