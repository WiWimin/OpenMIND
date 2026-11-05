"""联网检索（答案层后置补救）：资料无证据时的第二段回答数据源。

设计边界（验收方案 v2 · 第 2 点）：
- 只在**答案层**触发（ChatService 判定 insufficient_evidence 之后），
  不进入检索层 —— RAG 阈值/Judge 与负样本拦截口径不受影响；
- 评测脚本固定 `WEB_SEARCH_ENABLED=false` 以保基线口径；
- 任何失败（超时/解析不出/被墙）一律降级为「拒答回退」，绝不裸报错。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WebResult:
    title: str
    url: str
    snippet: str


# 子模块在此之后导入（bing/ddg 反向依赖 WebResult，避免循环导入）
from app.ai.websearch import bing, ddg  # noqa: E402  isort:skip


def web_search(query: str) -> list[WebResult]:
    """按配置的 provider 执行联网检索；关闭/失败返回空列表。"""
    from app.core.config import get_settings

    settings = get_settings()
    if not settings.web_search_enabled:
        return []
    provider = settings.web_search_provider.lower()
    try:
        if provider == "bing":
            return bing.search(
                query,
                max_results=settings.web_search_max_results,
                timeout_s=settings.web_search_timeout_s,
            )
        if provider == "ddg":
            return ddg.search(
                query,
                max_results=settings.web_search_max_results,
                timeout_s=settings.web_search_timeout_s,
            )
        logger.warning("未知的 WEB_SEARCH_PROVIDER=%s，跳过联网检索", provider)
        return []
    except Exception as exc:  # noqa: BLE001 —— 联网失败只降级，不阻断问答
        logger.warning("联网检索失败 provider=%s type=%s: %s", provider, type(exc).__name__, exc)
        return []
