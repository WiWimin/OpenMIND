from __future__ import annotations


def build_extract_action_items(context: dict) -> list[dict[str, str]]:
    records = context.get("record_transcripts", [])
    joined = "\n\n".join(records)
    system = (
        "你是会议助理。从会议记录中提取待办行动项。"
        "只输出 JSON 对象："
        '{"items": [{"content": "任务内容", "assignee": "负责人或 null", '
        '"due_date": "截止日期或 null", "source_record_id": "来源记录ID或 null", '
        '"source_excerpt": "原文摘录或 null"}]}。不要输出对象以外的内容。'
    )
    user = f"会议记录：\n{joined}"
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]
