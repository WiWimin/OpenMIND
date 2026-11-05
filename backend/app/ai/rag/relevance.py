"""检索相关性 Judge：对低分带候选做 LLM 复核。

背景（RAG 评测基线）：`min_score=0.3` 单阈值下，负样本 top1（0.31–0.48）与
正样本 top1（min 0.45）分数区间重叠，无法靠阈值分离。本模块在低分带引入
LLM 结构化判定：top1 分数低于 `rag_judge_min_score` 时复核其是否“直接包含
足以回答问题的信息”，判无关则整体拒答；Judge 不可用时回退分数判定，不阻断检索。
"""

from __future__ import annotations

import logging

from pydantic import BaseModel, Field

from app.services.model_config_service import ModelConfig, build_llm_client

logger = logging.getLogger(__name__)

_JUDGE_SYSTEM = (
    "你是检索相关性判定器。给定用户问题与若干候选内容，判断其中是否有任一候选"
    "直接包含足以回答问题的信息。只输出 JSON：{\"relevant\": true} 或 "
    "{\"relevant\": false}。判定标准：某个候选中存在可直接作答的事实或语句 → true；"
    "所有候选都仅主题相近、出现相关词汇但没有答案 → false。"
)

_MAX_EXCERPT_CHARS = 600
_MAX_CANDIDATES = 3


class RelevanceVerdict(BaseModel):
    relevant: bool = Field(description="候选内容能否直接回答问题")


class RelevanceJudge:
    def __init__(self, config: ModelConfig, client=None) -> None:
        # client 可注入（测试用 MockTransport 的 LLMClient）
        self._client = client if client is not None else build_llm_client(config)

    def is_relevant(self, query: str, excerpts: list[str]) -> bool | None:
        """判断候选中是否有任一可作答；Judge 不可用时返回 None。"""
        candidates = "\n\n".join(
            f"[候选 {index}] {text[:_MAX_EXCERPT_CHARS]}"
            for index, text in enumerate(excerpts[:_MAX_CANDIDATES], start=1)
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
                temperature=0,
                max_tokens=16,
            )
            return verdict.relevant
        except Exception as exc:  # noqa: BLE001 —— Judge 失败不得阻断检索
            logger.warning("RAG Judge 不可用，回退分数判定：%s", exc)
            return None
