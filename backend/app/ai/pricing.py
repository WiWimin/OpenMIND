"""模型调用成本估算（`ai-design.md 3.11`）。

按「模型名片段 → 每百万 token 单价（USD）」的静态价目表估算一次调用的成本，
用于 `ai_call_logs.cost_usd` 审计。价目为公开牌价的近似值，仅用于量级观测，
**不作为计费依据**；未命中价目的模型返回 `None`（日志成本列留空）。

日志红线：本模块只做数字运算，不接触提示词或用户内容。
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import NamedTuple


class Price(NamedTuple):
    """每 1M token 的 USD 单价。"""

    input_per_m: Decimal
    output_per_m: Decimal


def _p(input_per_m: str, output_per_m: str) -> Price:
    return Price(Decimal(input_per_m), Decimal(output_per_m))


# 按前缀匹配（长片段优先）：主流对话模型的公开牌价近似值
_PRICE_TABLE: tuple[tuple[str, Price], ...] = (
    ("gpt-4o-mini", _p("0.15", "0.60")),
    ("gpt-4o", _p("2.50", "10.00")),
    ("gpt-4.1-mini", _p("0.40", "1.60")),
    ("gpt-4.1", _p("2.00", "8.00")),
    ("o4-mini", _p("1.10", "4.40")),
    ("deepseek-chat", _p("0.27", "1.10")),
    ("deepseek-reasoner", _p("0.55", "2.19")),
    ("qwen-max", _p("2.40", "9.60")),
    ("qwen-plus", _p("0.40", "1.20")),
    ("qwen-turbo", _p("0.05", "0.20")),
    ("moonshot-v1-128k", _p("8.00", "8.00")),
    ("moonshot-v1-32k", _p("2.00", "2.00")),
    ("moonshot-v1-8k", _p("0.80", "0.80")),
    ("kimi-latest", _p("6.00", "6.00")),
)

# 成本金额保留 6 位小数（对齐 cost_usd Numeric(12,6)）
_COST_QUANT = Decimal("0.000001")


def price_for(model: str) -> Price | None:
    """按前缀匹配模型单价；未命中返回 None。"""
    name = (model or "").lower()
    if not name:
        return None
    # 长前缀优先，避免 "gpt-4o" 抢先匹配 "gpt-4o-mini"
    for prefix, price in sorted(_PRICE_TABLE, key=lambda item: -len(item[0])):
        if name.startswith(prefix):
            return price
    return None


def estimate_cost_usd(
    model: str, input_tokens: int | None, output_tokens: int | None
) -> Decimal | None:
    """估算一次调用的 USD 成本；单价未知或无用量时返回 None。"""
    price = price_for(model)
    if price is None:
        return None
    in_tokens = max(0, input_tokens or 0)
    out_tokens = max(0, output_tokens or 0)
    if in_tokens == 0 and out_tokens == 0:
        return None
    cost = (
        Decimal(in_tokens) * price.input_per_m
        + Decimal(out_tokens) * price.output_per_m
    ) / Decimal(1_000_000)
    return cost.quantize(_COST_QUANT, rounding=ROUND_HALF_UP)
