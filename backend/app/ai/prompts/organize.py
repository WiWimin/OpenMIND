from __future__ import annotations


def build_organize(context: dict) -> list[dict[str, str]]:
    records = context.get("record_transcripts", [])
    joined = "\n\n".join(records)
    system = (
        "你是会议助理，负责整理会议记录，使其逻辑清晰、去除口语冗余。"
        "直接输出整理后的正文，不要输出 JSON。"
    )
    user = f"原始记录：\n{joined}"
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]
