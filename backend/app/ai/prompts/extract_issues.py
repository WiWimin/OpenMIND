from __future__ import annotations


def build_extract_issues(context: dict) -> list[dict[str, str]]:
    records = context.get("record_transcripts", [])
    joined = "\n\n".join(records)
    system = (
        "你是会议助理。从会议记录中提取尚未解决的问题。"
        "只输出 JSON 数组，每个元素为："
        '{"description": "问题描述", "follow_up": "后续跟进或 null", '
        '"source_record_id": "来源记录ID或 null"}。不要输出数组以外的内容。'
    )
    user = f"会议记录：\n{joined}"
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]
