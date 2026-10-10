from __future__ import annotations

from pydantic import BaseModel

from app.ai.llm import LLMClient
from app.ai.prompts import build_prepare


class PreparationDraft(BaseModel):
    summary: str
    checklist: list[str]


class PreparationService:
    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm

    def generate(self, meeting_topic: str, material_snippets: list[str]) -> PreparationDraft:
        messages = build_prepare(
            {"meeting_topic": meeting_topic, "material_snippets": material_snippets}
        )
        return self.llm.chat_json(messages, schema=PreparationDraft)
