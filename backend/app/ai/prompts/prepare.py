from __future__ import annotations


def build_prepare(context: dict) -> list[dict[str, str]]:
    topic = context.get("meeting_topic", "")
    snippets = context.get("material_snippets", [])
    joined = "\n\n".join(snippets)
    system = (
        "你是会议助理，负责生成会前准备稿。"
        "根据会议主题与材料片段，只输出 JSON："
        '{"summary": "会议摘要", "checklist": ["准备事项1", "准备事项2"]}。'
        "不要输出 JSON 以外的内容。"
    )
    user = f"会议主题：{topic}\n\n材料片段：\n{joined}"
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]
