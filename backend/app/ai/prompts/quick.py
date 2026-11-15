"""简单文本任务（quick_task）：单次 LLM、无检索、无落库、无确认门。

对应执行通道 `prompt`（`docs/agent-framework.md 4.2`）。四类任务只改变表达，
不改变事实与结论；输出为纯文本，由前端直接展示或复制，不写回原始记录。

与 `organize` 的分工：`organize` 是「整理会议记录」的结构化整理链（可带来源、
可走 summary/polish 结构化输出）；`quick_task` 只处理用户选中的一段文本。
"""

from __future__ import annotations

_TASK_SYSTEM: dict[str, str] = {
    "polish": (
        "你是中文文本润色助手。在不改变原意、不新增事实的前提下，"
        "修正病句、口语冗余、标点与错别字，使表达更清晰专业。"
        "保留原文的人名、数字、时间与专有名词。直接输出润色后的正文，不要解释修改理由。"
    ),
    "condense": (
        "你是中文文本压缩助手。把输入压缩到原长度的 40%-60%，"
        "只保留结论、关键数据与待办，删除铺垫与重复表述。"
        "不新增原文没有的信息。直接输出压缩后的正文，不要解释。"
    ),
    "rewrite": (
        "你是中文改写助手。按用户要求重写输入文本，保持事实不变、结构可调整。"
        "若用户未给出具体要求，改写为更书面、条理更清晰的版本。"
        "直接输出改写后的正文，不要解释。"
    ),
    "translate": (
        "你是翻译助手。把输入文本翻译成目标语言；用户未指定时默认译为英文。"
        "保留专有名词、数字与格式，不增删信息。"
        "直接输出译文，不要附加原文或解释。"
    ),
}


def build_quick_task(context: dict) -> list[dict[str, str]]:
    task = str(context.get("task") or "polish")
    system = _TASK_SYSTEM.get(task, _TASK_SYSTEM["polish"])
    text = str(context.get("text") or "").strip()
    instruction = str(context.get("instruction") or "").strip()

    user = f"待处理文本：\n{text}"
    if instruction:
        user += f"\n\n用户补充要求：{instruction}"
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]
