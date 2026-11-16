"""会前速览（brief）生成：只读本场资料，输出结构化摘要卡。

边界（`docs/agent-framework.md 4.2`）：

- 只调用 LLM，不写业务表、不产文件、不覆盖原文；
- 输出由 `MaterialBrief` 做长度收口，保证前端卡片始终可渲染；
- 资料为空时不调用模型，由调用方返回「暂无可速览资料」。
"""

from __future__ import annotations

from dataclasses import dataclass

from app.ai.llm import LLMClient
from app.ai.prompts import build_brief
from app.ai.structured import run_structured
from app.schemas.chat import MaterialBrief


@dataclass(frozen=True)
class BriefMaterial:
    """参与速览的资料片段（已由 service 层做权限与长度裁剪）。"""

    material_id: str | None
    name: str | None
    content: str


def _validate_brief(brief: MaterialBrief) -> list[str]:
    """业务字段校验：一句话速览必须有内容；其余维度允许为空。"""
    errors: list[str] = []
    if not brief.headline.strip():
        errors.append("headline 不能为空")
    return errors


class MaterialBriefService:
    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm

    def generate(
        self,
        *,
        meeting_topic: str,
        materials: list[BriefMaterial],
        user_goal: str = "",
    ) -> MaterialBrief:
        snippets = [
            f"【{material.name or '资料'}】\n{material.content}"
            for material in materials
            if material.content.strip()
        ]
        messages = build_brief(
            {
                "meeting_topic": meeting_topic,
                "material_snippets": snippets,
                "user_goal": user_goal,
            }
        )
        return run_structured(
            lambda msgs: self.llm.chat_json(msgs, schema=MaterialBrief, scene="brief"),
            messages,
            MaterialBrief,
            scene="brief",
            validator=_validate_brief,
        )
