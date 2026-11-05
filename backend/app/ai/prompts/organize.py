from __future__ import annotations


# 整理任务（task=organize）：支持 style 风格覆盖
def _organize_system(style: str) -> str:
    system = "你是会议助理，负责整理会议记录，使其逻辑清晰、去除口语冗余。"
    if style:
        system += f"整理风格要求：{style}。"
    system += "保持原意，不添加原内容之外的信息。直接输出整理后的正文，不要输出 JSON。"
    return system


# 提炼要点（task=summary）：严格 JSON，供前端结构化渲染
_SUMMARY_SYSTEM = (
    "你是会议纪要助手。请从会议内容中提取结构化信息。"
    "严格输出 JSON 对象，不要输出 JSON 以外的任何文字，不要输出 markdown 代码块标记，格式："
    '{"conclusion": ["本次会议达成的核心结论，每条一句话"], '
    '"key_discussions": [{"topic": "议题", "points": ["关键讨论点"]}], '
    '"action_items": [{"task": "具体任务（动宾结构）", '
    '"assignee": "责任人称谓（保留原文）或 null", '
    '"deadline": "YYYY-MM-DD 或原文表述或 null", "priority": "high/medium/low", '
    '"source_quote": "原文中说出这条待办的原句或 null"}], '
    '"open_questions": ["讨论了但没有结论、下次需要继续的问题"]}'
    "规则：只提取明确出现的信息，禁止臆造；内容中没有的维度用空数组。"
    "action_items 必须是明确的执行性语句，纯讨论不算；"
    "priority 按 今天/明天要做=high、本周内=medium、下周及以后=low 判定；"
    "source_quote 必须摘自原文。"
)

# 简短摘要（task=brief）：正文输出
def _brief_system(style: str) -> str:
    system = (
        "你是会议助理，负责给出会议内容的简短摘要。"
        "用 3-5 句话概括当前进展，覆盖已完成讨论、当前结论与下一步方向；"
        "不展开细节，不编造。"
    )
    if style:
        system += f"风格要求：{style}。"
    system += "直接输出正文，不要输出 JSON。"
    return system


# 修正口误（task=polish）：严格 JSON diff，由用户逐条确认
_POLISH_SYSTEM = (
    "你是 ASR 转写文本校对助手。请从会议转写文本中识别可能的口误、语音识别错误和不通顺之处。"
    "严格输出 JSON 数组，不要输出 JSON 以外的任何文字，不要输出 markdown 代码块标记，每条格式："
    '[{"location": "该句开头的前 10 个字（仅用于定位展示）", "original": "原文片段", '
    '"suggested": "建议改成的内容", "reason": "修改理由（一句话）", '
    '"confidence": "high/medium/low"}]'
    "规则：只改明显的口误、语音识别错误、同音错字；不要润色文风、不要改语义；"
    "每条修改保持在原文同一行内，不要引入换行；"
    "不确定的不要提，宁可少改不要错改；完全通顺的段落不要动；"
    "没有可修改之处就输出空数组 []。"
)


def build_organize(context: dict) -> list[dict[str, str]]:
    task = context.get("task", "organize")
    joined = "\n\n".join(context.get("record_transcripts", []))
    style = context.get("style", "")
    instruction = (context.get("instruction") or "").strip()

    if task == "summary":
        system = _SUMMARY_SYSTEM
    elif task == "brief":
        system = _brief_system(style)
    elif task == "polish":
        system = _POLISH_SYSTEM
    else:
        system = _organize_system(style)

    user = f"会议内容：\n{joined}"
    if instruction:
        user += f"\n\n用户补充要求：{instruction}"
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]
