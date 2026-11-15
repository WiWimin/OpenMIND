"""会前速览（brief）：把本场会议资料压缩成一张可快速浏览的摘要卡。

与 `prepare` 的分工（`docs/agent-framework.md 10.2`）：

- `brief` 只回答「这场会要谈什么、我需要知道什么」，面向会前 60 秒速读；
- `prepare` 负责「我要做什么准备」，输出准备稿 + 清单；
- 两者都只读本场资料，不产文件、不落库、不覆盖原文。

长度约束与 `schemas/chat.py::MaterialBrief` 一致：总字数 ≤300，
headline ≤40、key_points ≤5×40、decisions ≤3×30、risks ≤2×30、next_step ≤40。
提示词负责「尽量一次写对」，schema 负责「超长确定性截断」。
"""

from __future__ import annotations

_BRIEF_SYSTEM = (
    "你是会议速览助手，为参会人提供会前 60 秒可读完的速览。"
    "严格输出 JSON 对象，不要输出 JSON 以外的任何文字，不要输出 markdown 代码块标记，格式："
    '{"headline": "一句话说明这场会要解决的核心问题（≤40 字）", '
    '"key_points": ["3-5 条参会人必须知道的关键信息，每条 ≤40 字"], '
    '"decisions_needed": ["会上需要拍板的事项，最多 3 条，每条 ≤30 字"], '
    '"risks": ["已知风险或阻碍，最多 2 条，每条 ≤30 字"], '
    '"next_step": "会前最该做的一件事（≤40 字）"}'
    "硬性规则："
    "1) 所有字段合计不超过 300 字，宁少勿多；"
    "2) 只使用给定资料中的事实，资料没有的维度输出空数组或空字符串，禁止臆造；"
    "3) 不要输出准备清单、待办清单或会议纪要结构，清单类内容交给「准备清单」；"
    "4) key_points 写「是什么」，不要写「要做什么」；"
    "5) 资料中若存在冲突信息，写进 risks，不要自行裁决；"
    "6) 不要复述资料原文长句，用参会人视角改写为结论句。"
)


def build_brief(context: dict) -> list[dict[str, str]]:
    topic = (context.get("meeting_topic") or "").strip()
    snippets = context.get("material_snippets") or []
    joined = "\n\n".join(snippet for snippet in snippets if snippet)
    user_goal = (context.get("user_goal") or "").strip()

    user = f"会议主题：{topic or '（未填写）'}\n\n本场资料：\n{joined or '（暂无资料）'}"
    if user_goal:
        user += f"\n\n用户关注点（只影响取舍，不改变输出格式）：{user_goal}"
    return [{"role": "system", "content": _BRIEF_SYSTEM}, {"role": "user", "content": user}]
