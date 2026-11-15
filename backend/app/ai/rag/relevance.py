"""检索相关性 Judge：对低分带候选做 LLM 复核。

背景（RAG 评测基线）：`min_score=0.3` 单阈值下，负样本 top1（0.31–0.48）与
正样本 top1（min 0.45）分数区间重叠，无法靠阈值分离。本模块在低分带引入
LLM 结构化判定：top1 分数低于 `rag_judge_min_score` 时复核其是否“直接包含
足以回答问题的信息”，判无关则整体拒答；Judge 不可用时回退分数判定，不阻断检索。
"""

from __future__ import annotations

import logging
import re

from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.services.model_config_service import ModelConfig, build_llm_client

logger = logging.getLogger(__name__)

# 词面预筛：问题 bigram 被候选覆盖的比例（0~1）。无向量索引的记录相关性用
RECORD_MIN_SCORE = 0.3


def _bigrams(text: str) -> set[str]:
    compact = re.sub(r"\s+", "", text or "").lower()
    if len(compact) < 2:
        return {compact} if compact else set()
    return {compact[index : index + 2] for index in range(len(compact) - 1)}


def char_overlap(query: str, text: str) -> float:
    """问题 bigram 被文本覆盖的比例（0~1），用于无向量索引时的词面预筛。

    用「覆盖率」而非 Jaccard：文本（会议记录）远长于问题，Jaccard 会被
    长度稀释到接近 0，无法区分相关与无关。问题为空或 bigram 不足 2 个时
    返回 1.0（不做过滤），避免空问句/超短问句被误判为「无证据」。
    """
    left = _bigrams(query)
    if len(left) < 2:
        return 1.0  # 过短的问句（「结论？」）不做词面过滤，交由调用方兜底
    right = _bigrams(text)
    if not right:
        return 0.0
    return len(left & right) / len(left)


def is_lexically_relevant(query: str, text: str) -> bool:
    """按 `RECORD_MIN_SCORE` 判定词面相关。"""
    return char_overlap(query, text) >= RECORD_MIN_SCORE

_JUDGE_SYSTEM = (
    "你是检索相关性判定器。给定用户问题与若干候选内容，判断其中是否有任一候选"
    "直接包含足以回答问题的信息。只输出 JSON：{\"relevant\": true} 或 "
    "{\"relevant\": false}。判定标准：某个候选中存在可直接作答的事实或语句 → true；"
    "所有候选都仅主题相近、出现相关词汇但没有答案 → false。"
)


class RelevanceVerdict(BaseModel):
    relevant: bool = Field(description="候选内容能否直接回答问题")


class RelevanceJudge:
    def __init__(self, config: ModelConfig, client=None) -> None:
        # client 可注入（测试用 MockTransport 的 LLMClient）
        self._client = client if client is not None else build_llm_client(config)

    def is_relevant(self, query: str, excerpts: list[str]) -> bool | None:
        """判断候选中是否有任一可作答；Judge 不可用时返回 None。"""
        settings = get_settings()
        max_excerpt_chars = settings.rag_judge_max_excerpt_chars
        max_candidates = settings.rag_judge_top_candidates
        candidates = "\n\n".join(
            f"[候选 {index}] {text[:max_excerpt_chars]}"
            for index, text in enumerate(excerpts[:max_candidates], start=1)
        )
        try:
            verdict = self._client.chat_json(
                [
                    {"role": "system", "content": _JUDGE_SYSTEM},
                    {
                        "role": "user",
                        "content": f"问题：{query}\n\n{candidates}",
                    },
                ],
                schema=RelevanceVerdict,
                scene="rag_judge",
            )
            return verdict.relevant
        except Exception as exc:  # noqa: BLE001 —— Judge 失败不得阻断检索
            logger.warning("RAG Judge 不可用，回退分数判定：%s", exc)
            return None
