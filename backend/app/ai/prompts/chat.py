from __future__ import annotations


def build_chat(context: dict) -> list[dict[str, str]]:
    question = context.get("question", "")
    contexts = context.get("contexts", [])
    joined = "\n\n".join(contexts)
    system = (
        "你是会议助理，基于提供的会议材料回答用户问题。"
        "若材料不足以回答，请明确说明无法确认，不要编造。直接输出回答，不要输出 JSON。"
    )
    user = f"问题：{question}\n\n相关资料：\n{joined}"
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]
