from __future__ import annotations

_MARKER_LABELS = {
    "highlight": "重点",
    "decision": "决议",
    "question": "疑问",
}

_TEMPLATE_INSTRUCTIONS = {
    "standard": "生成结构清晰的会议纪要，包含议题、讨论要点与结论。",
    "concise": "生成简洁记录，只保留关键结论、决议和待办，优先使用短段落或要点。",
    "task_list": (
        "生成任务清单，按任务列出负责人和截止时间；"
        "未提及负责人或截止时间时写“未指定”，不得编造。"
    ),
}


def build_minutes(context: dict) -> list[dict[str, str]]:
    topic = context.get("meeting_topic", "")
    records = context.get("record_transcripts", [])
    materials = context.get("material_snippets", [])
    marked = context.get("marked_records", [])
    template = context.get("template", "standard")
    joined_records = "\n\n".join(records)
    joined_materials = "\n\n".join(materials)
    marked_lines = "\n".join(
        f"[{_MARKER_LABELS.get(item.get('marker_type', ''), '标记')}] "
        f"{item.get('content', '')}"
        for item in marked
    )
    instruction = _TEMPLATE_INSTRUCTIONS.get(
        template, _TEMPLATE_INSTRUCTIONS["standard"]
    )
    system = (
        f"你是会议纪要助手。{instruction}"
        "根据会议资料、会议记录和用户标记生成内容；资料只作背景，"
        "不得把资料中没有的信息写成会议事实。"
        "直接输出正文，不要输出 JSON。"
    )
    user = (
        f"会议主题：{topic}\n\n"
        f"会议资料（仅作背景）：\n{joined_materials}\n\n"
        f"会议记录：\n{joined_records}\n\n"
        f"用户标记：\n{marked_lines}"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]
