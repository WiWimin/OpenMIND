"""问答执行步骤（trace）：给前端展示「真实推理链」。

只描述服务端真实发生过的阶段（理解意图 → 检索 → 生成），
不伪造模型内部推理；模型原生推理由 `event: reasoning` 单独下发。
"""

from __future__ import annotations

from typing import Any

INTENT_LABELS: dict[str, str] = {
    "chat": "会议问答",
    "knowledge_search": "知识库问答",
    "web_search": "联网检索",
    "prepare": "生成会前准备稿",
    "minutes_generate": "生成会议纪要",
    "action_items_extract": "提取行动项",
    "issues_extract": "梳理未解决问题",
    "organize": "整理记录",
    "brief": "生成会前速览",
    "build_file": "生成可交付文件",
    "transcribe": "转写录音",
    "clarify": "澄清问题",
    "help": "说明可用能力",
}

SCOPE_LABELS: dict[str, str] = {
    "current_meeting": "检索会议资料",
    "current_and_history": "检索当前与历史会议",
    "knowledge_base": "检索个人知识库",
}


def intent_label(intent: str | None) -> str:
    """意图 → 展示文案；未登记意图用通用文案，不暴露内部枚举。"""
    return INTENT_LABELS.get(intent or "", "会议问答")


def retrieval_stage(scope: str | None, hits: int) -> dict[str, Any]:
    """检索阶段：命中数是真实结果，不夸大、不伪造。"""
    label = SCOPE_LABELS.get(scope or "", SCOPE_LABELS["current_meeting"])
    detail = f"命中 {hits} 条相关片段" if hits else "未命中相关片段"
    return {"id": "retrieve", "label": label, "status": "done", "detail": detail}


def build_chat_trace(
    *,
    intent: str | None,
    scope: str | None,
    hits: int,
    native: bool,
) -> dict[str, Any]:
    """问答 trace：理解 → 检索 → 生成（generate 初始为 running）。"""
    return {
        "stages": [
            {
                "id": "intent",
                "label": "理解问题",
                "status": "done",
                "detail": intent_label(intent),
            },
            retrieval_stage(scope, hits),
            {"id": "generate", "label": "生成回答", "status": "running"},
        ],
        "native_reasoning": native,
    }
