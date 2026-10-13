from __future__ import annotations

from pydantic import BaseModel

from app.ai.llm import LLMClient
from app.ai.prompts import build_extract_action_items, build_extract_issues


class ActionItemCandidate(BaseModel):
    content: str
    assignee: str | None = None
    due_date: str | None = None
    source_record_id: str | None = None
    source_excerpt: str | None = None


class ActionItemsResult(BaseModel):
    items: list[ActionItemCandidate]


class IssueCandidate(BaseModel):
    description: str
    follow_up: str | None = None
    source_record_id: str | None = None


class IssuesResult(BaseModel):
    items: list[IssueCandidate]


class ActionItemExtractor:
    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm

    def extract(self, record_transcripts: list[str]) -> list[ActionItemCandidate]:
        messages = build_extract_action_items({"record_transcripts": record_transcripts})
        return self.llm.chat_json(messages, schema=ActionItemsResult).items


class IssueExtractor:
    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm

    def extract(self, record_transcripts: list[str]) -> list[IssueCandidate]:
        messages = build_extract_issues({"record_transcripts": record_transcripts})
        return self.llm.chat_json(messages, schema=IssuesResult).items
