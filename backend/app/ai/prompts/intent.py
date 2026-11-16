from __future__ import annotations

from app.schemas.agent import AgentIntent


def build_intent(context: dict) -> list[dict[str, str]]:
    """意图路由：把用户一句话映射到受控意图白名单（只输出 JSON）。"""
    message = context.get("message", "")
    scene = context.get("scene", "minutes")
    meeting_state = context.get("meeting_state", "")
    intents = ", ".join(intent.value for intent in AgentIntent)
    system = (
        "你是会议助理的意图路由器。请把用户消息归类到下列意图之一：\n"
        f"{intents}\n"
        "规则：\n"
        "1. 只输出 JSON，不要 markdown 代码块或额外文字；\n"
        "2. 字段：intent（白名单值）、confidence（0-1）、"
        "slots（可选，字符串字典）、needs_clarification（布尔）、"
        "clarification_question（需要澄清时的一句话）；\n"
        "3. 用户只是提问/闲聊 → chat；要求生成纪要点 → minutes_generate；"
        "要求整理记录 → organize；要求提取待办 → action_items_extract；"
        "要求提取未解决问题/风险 → issues_extract；要求生成会前准备 → prepare；"
        "要求会前速览/资料摘要/概括本场资料 → brief；"
        "明确要求联网查外部信息 → web_search；要求导出可交付文件 → build_file；"
        "要求转写录音 → transcribe；信息不足无法判断 → clarify；\n"
        "4. 页面只作为弱先验，不得覆盖用户明确表达；\n"
        "5. 不得编造会议事实，slots 只放用户明确提到的信息。"
    )
    user = (
        f"页面场景：{scene}\n"
        f"会议状态：{meeting_state or '未知'}\n"
        f"用户消息：{message}"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]
