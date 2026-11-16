"""同 provider 备用模型链的通用实现（`ai-design.md 3.9`）。

被 LLM（`ai/llm/chain.py`）与音频转写（`ai/transcription/client.py`）共用：
候选构造、链长上限、触发降级的错误类别都与「哪个能力」无关。

链是**同 provider** 的——备用模型与主模型共用 `api_base/api_key`，只换模型名。
调用方传入自己的 `raw`（如 `LLM_FALLBACK_MODELS` / `ASR_FALLBACK_MODELS`），
本模块不读配置，便于测试注入。

**触发降级的错误**（模型维度问题，换模型有意义）：

- `MODEL_QUOTA_EXCEEDED` —— 该模型额度耗尽；
- `MODEL_INPUT_TOO_LONG` —— 该模型上下文窗口不够（备用模型可能更大）；
- `MODEL_UPSTREAM_UNAVAILABLE` —— 该模型熔断打开（熔断键含 model，备用模型独立）；
- `MODEL_TIMEOUT` —— 该模型持续超时/过载。

**不降级**：`MODEL_CONFIG_INVALID`（密钥问题对所有模型一致）、`RATE_LIMITED`
（限流通常按 key）、`INTERNAL_ERROR`（网络/网关问题与模型无关）、
`MODEL_OUTPUT_INVALID`（换模型不改变请求语义）、4xx 请求错误。

`probe()` 不走降级——配置校验必须验证用户所选的那个模型。
"""

from __future__ import annotations

from app.core.exceptions import AppError

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


def parse_fallback_models(raw: str | None) -> list[str]:
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


def configured_chain(primary: str | None, raw: str | None) -> list[str]:
    """读取配置原文构造当前生效的候选链。"""
    return build_chain(primary, parse_fallback_models(raw))
