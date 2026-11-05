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


def build_web_chat(context: dict) -> list[dict[str, str]]:
    """资料无证据时的联网回答：基于检索片段作答并标注来源编号。"""
    question = context.get("question", "")
    sources = context.get("sources", [])
    blocks = []
    for index, source in enumerate(sources, start=1):
        title = source.get("title", "")
        snippet = source.get("snippet", "")
        url = source.get("url", "")
        blocks.append(f"[{index}] {title}\n{snippet}\n链接：{url}")
    joined = "\n\n".join(blocks)
    system = (
        "你的会议资料中未找到该问题的证据。现在改用联网检索片段回答，要求：\n"
        "1. 只依据给定片段作答，不得编造片段之外的事实；\n"
        "2. 回答中引用片段时用 [编号] 标注来源；\n"
        "3. 片段不足以给出结论时，明确说明仍无法确定，不要臆测；\n"
        "4. 直接输出回答正文，不要输出 JSON。"
    )
    user = f"问题：{question}\n\n联网检索片段：\n{joined}"
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def build_deliverable(context: dict) -> list[dict[str, str]]:
    """Build 模式：基于资料生成可交付文件（结构化 JSON 输出）。"""
    question = context.get("question", "")
    contexts = context.get("contexts", [])
    memory = context.get("memory_context", "")
    joined = "\n\n".join(contexts)
    system = (
        "你是个人会议助理，负责把会议资料整理成可交付文件。要求：\n"
        "1. 严格依据给定资料作答，不要编造资料之外的事实；\n"
        "2. 输出 JSON（无代码块包裹），字段：\n"
        "   - summary：给用户的简短说明（1-3 句，说明做了什么）；\n"
        "   - filename：文件名（不含路径，建议 .md 后缀，语义化命名）；\n"
        "   - content_md：文件正文，结构化 Markdown（标题/列表/表格按内容选择），"
        "内容完整可用于直接交付；\n"
        "3. 用户画像仅影响表达风格，不得覆盖事实。"
    )
    user = f"需求：{question}\n\n"
    if memory:
        user += f"用户画像：\n{memory}\n\n"
    user += f"资料：\n{joined}"
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]
