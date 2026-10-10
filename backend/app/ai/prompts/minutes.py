from __future__ import annotations


def build_minutes(context: dict) -> list[dict[str, str]]:
    topic = context.get("meeting_topic", "")
    records = context.get("record_transcripts", [])
    joined = "\n\n".join(records)
    system = (
        "你是会议纪要助手。根据会议记录生成结构清晰的会议纪要正文，"
        "包含议题、讨论要点与结论。直接输出正文，不要输出 JSON。"
    )
    user = f"会议主题：{topic}\n\n会议记录：\n{joined}"
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]
