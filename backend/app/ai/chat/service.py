from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from app.ai.llm import LLMClient
from app.ai.prompts import build_chat


@dataclass(frozen=True)
class Source:
    meeting_id: str
    material_id: str
    record_id: str | None
    excerpt: str


@dataclass(frozen=True)
class ChatAnswer:
    answer: str
    sources: list[Source]
    insufficient_evidence: bool


class Retriever(Protocol):
    def retrieve(
        self,
        query: str,
        *,
        user_id: str,
        scope: str = "current_meeting",
        current_meeting_id: str | None = None,
        top_k: int = 5,
        min_score: float = 0.3,
    ) -> list[Any]: ...


class ChatService:
    def __init__(self, llm: LLMClient, retriever: Retriever) -> None:
        self.llm = llm
        self.retriever = retriever

    def answer(
        self,
        question: str,
        *,
        user_id: str,
        scope: str = "current_meeting",
        current_meeting_id: str | None = None,
    ) -> ChatAnswer:
        chunks = self.retriever.retrieve(
            question,
            user_id=user_id,
            scope=scope,
            current_meeting_id=current_meeting_id,
        )
        if not chunks:
            return ChatAnswer(
                answer="根据现有材料无法确认该问题的答案。",
                sources=[],
                insufficient_evidence=True,
            )
        contexts = [chunk.excerpt for chunk in chunks]
        messages = build_chat({"question": question, "contexts": contexts})
        answer = self.llm.chat(messages).text
        sources = [
            Source(
                meeting_id=chunk.meeting_id,
                material_id=chunk.material_id,
                record_id=chunk.record_id,
                excerpt=chunk.excerpt,
            )
            for chunk in chunks
        ]
        return ChatAnswer(answer=answer, sources=sources, insufficient_evidence=False)
