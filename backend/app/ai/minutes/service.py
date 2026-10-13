from __future__ import annotations

from app.ai.llm import LLMClient
from app.ai.prompts import build_minutes


class MinutesService:
    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm

    def generate(self, meeting_topic: str, record_transcripts: list[str]) -> str:
        messages = build_minutes(
            {"meeting_topic": meeting_topic, "record_transcripts": record_transcripts}
        )
        return self.llm.chat(messages).text
