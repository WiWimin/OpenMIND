from __future__ import annotations

from app.ai.llm import LLMClient
from app.ai.prompts import build_minutes


class MinutesService:
    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm

    def generate(
        self,
        meeting_topic: str,
        record_transcripts: list[str],
        material_snippets: list[str] | None = None,
        marked_records: list[dict[str, str]] | None = None,
        *,
        template: str = "standard",
        memory_context: str = "",
        template_instructions: str = "",
    ) -> str:
        messages = build_minutes(
            {
                "meeting_topic": meeting_topic,
                "record_transcripts": record_transcripts,
                "material_snippets": material_snippets or [],
                "marked_records": marked_records or [],
                "template": template,
                "memory_context": memory_context,
                "template_instructions": template_instructions,
            }
        )
        return self.llm.chat(messages).text
