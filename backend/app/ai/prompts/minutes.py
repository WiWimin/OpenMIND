from __future__ import annotations

_MARKER_LABELS = {
    "highlight": "重点",
    "decision": "决议",
    "question": "疑问",
}


def build_minutes(context: dict) -> list[dict[str, str]]:
    topic = context.get("meeting_topic", "")
    records = context.get("record_transcripts", [])
    materials = context.get("material_snippets", [])
    marked = context.get("marked_records", [])
    joined_records = "\n\n".join(records)
    joined_materials = "\n\n".join(materials)
    marked_lines = "\n".join(
        f"[{_MARKER_LABELS.get(item.get('marker_type', ''), '标记')}] "
        f"{item.get('content', '')}"
        for item in marked
    )
    system = (
        "你是会议纪要助手。根据会议资料、会议记录和用户标记生成结构清晰的会议纪要正文，"
        "包含议题、讨论要点与结论。不得把资料中没有的信息写成会议事实。"
        "直接输出正文，不要输出 JSON。"
    )
    user = (
        f"会议主题：{topic}\n\n"
        f"会议资料（仅作背景）：\n{joined_materials}\n\n"
        f"会议记录：\n{joined_records}\n\n"
        f"用户标记：\n{marked_lines}"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]
