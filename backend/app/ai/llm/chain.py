"""LLM 模型降级链（`ai-design.md 3.9`）。

`LLM_FALLBACK_MODELS`（逗号分隔，**同 provider**——与主模型共用 `api_base/api_key`）
配置一组备用模型名。主模型调用失败且错误属于「换模型可能解决」的类别时，
按序切换到下一个候选继续调用；全部失败则抛最后一次错误。

**触发降级的错误**（模型维度问题，换模型有意义）：

- `MODEL_QUOTA_EXCEEDED` —— 该模型额度耗尽；
- `MODEL_INPUT_TOO_LONG` —— 该模型上下文窗口不够（备用模型可能更大）；
- `MODEL_UPSTREAM_UNAVAILABLE` —— 该模型熔断打开（熔断键含 model，备用模型独立）；
- `MODEL_TIMEOUT` —— 该模型持续超时/过载。

**不降级**：`MODEL_CONFIG_INVALID`（密钥问题对所有模型一致）、`RATE_LIMITED`
（限流通常按 key）、`INTERNAL_ERROR`（网络/网关问题与模型无关）、
`MODEL_OUTPUT_INVALID`（换模型不改变请求语义）、4xx 请求错误。

仅在**非显式指定模型**时生效有限制的说法不成立：链是服务端可用性兜底，
请求级 `model` 覆盖同样参与（覆盖值作为链首）。`probe()` 不走降级——
配置校验必须验证用户所选的那个模型。
"""

from __future__ import annotations

import logging

from app.core.config import get_settings
from app.core.exceptions import AppError

logger = logging.getLogger(__name__)

# 换模型可能解决的错误类别
FALLBACK_ERROR_CODES = frozenset(
    {
        "MODEL_QUOTA_EXCEEDED",
        "MODEL_INPUT_TOO_LONG",
        "MODEL_UPSTREAM_UNAVAILABLE",
        "MODEL_TIMEOUT",
    }
)

# 链长上限（含主模型）：控制最坏情况的总耗时
MAX_CHAIN_LENGTH = 4


def parse_fallback_models(raw: str) -> list[str]:
    """解析逗号分隔的备用模型列表：去空白、去重、保序。"""
    seen: list[str] = []
    for part in (raw or "").split(","):
        name = part.strip()
        if name and name not in seen:
            seen.append(name)
    return seen


def should_fall_back(exc: AppError) -> bool:
    """该错误是否值得换下一个模型重试。"""
    return exc.error_code in FALLBACK_ERROR_CODES


def build_chain(primary: str | None, fallbacks: list[str]) -> list[str]:
    """构造候选链：主模型在首，备用模型去重跟随，总长截断。"""
    chain: list[str] = []
    for name in (primary, *fallbacks):
        if name and name not in chain:
            chain.append(name)
        if len(chain) >= MAX_CHAIN_LENGTH:
            break
    return chain


def configured_chain(primary: str | None) -> list[str]:
    """读取 `LLM_FALLBACK_MODELS` 构造当前生效的候选链。"""
    return build_chain(primary, parse_fallback_models(get_settings().llm_fallback_models))
