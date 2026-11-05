from __future__ import annotations

from pydantic import BaseModel

from app.ai.llm import LLMClient
from app.ai.prompts import build_prepare
from app.ai.structured import run_structured


class PreparationDraft(BaseModel):
    summary: str
    checklist: list[str]


def _validate_preparation(draft: PreparationDraft) -> list[str]:
    """业务字段校验：摘要非空；清单允许为空数组，但元素须非空。"""
    errors: list[str] = []
    if not draft.summary.strip():
        errors.append("summary 不能为空")
    for index, item in enumerate(draft.checklist):
        if not item.strip():
            errors.append(f"checklist.{index} 不能为空")
    return errors


class PreparationService:
    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm

    def generate(
        self,
        meeting_topic: str,
        material_snippets: list[str],
        *,
        memory_context: str = "",
        template_instructions: str = "",
    ) -> PreparationDraft:
        messages = build_prepare(
            {
                "meeting_topic": meeting_topic,
                "material_snippets": material_snippets,
                "memory_context": memory_context,
                "template_instructions": template_instructions,
            }
        )
        return run_structured(
            lambda msgs: self.llm.chat_json(msgs, schema=PreparationDraft),
            messages,
            PreparationDraft,
            scene="prepare",
            validator=_validate_preparation,
        )
