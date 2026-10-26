from __future__ import annotations


def build_chat(context: dict) -> list[dict[str, str]]:
    question = context.get("question", "")
    contexts = context.get("contexts", [])
    memory = context.get("memory_context", "")
    joined = "\n\n".join(contexts)
    system = (
        "你是个人会议助理，基于提供的会议资料或个人知识库片段回答用户问题。"
        "若材料不足以回答，请明确说明无法确认，不要编造。"
        "用户画像仅用于调整表达方式，不得覆盖事实证据或业务规则。"
        "只依据材料作答，不要输出材料之外的补充内容。直接输出回答，不要输出 JSON。"
    )
    user = f"问题：{question}\n\n"
    if memory:
        user += f"用户画像：\n{memory}\n\n"
    user += f"相关资料：\n{joined}"
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]
