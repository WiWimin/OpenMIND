from __future__ import annotations

from pydantic import BaseModel

from app.ai.llm import LLMClient
from app.ai.prompts import build_extract_action_items, build_extract_issues
from app.ai.structured import run_structured


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


def _validate_action_items(result: ActionItemsResult) -> list[str]:
    """业务字段校验：任务内容非空，来源摘录非空时须非空白。"""
    errors: list[str] = []
    for index, item in enumerate(result.items):
        if not item.content.strip():
            errors.append(f"items.{index}.content 不能为空")
        if item.source_excerpt is not None and not item.source_excerpt.strip():
            errors.append(f"items.{index}.source_excerpt 为空时应使用 null")
    return errors


def _validate_issues(result: IssuesResult) -> list[str]:
    """业务字段校验：问题描述非空。"""
    errors: list[str] = []
    for index, item in enumerate(result.items):
        if not item.description.strip():
            errors.append(f"items.{index}.description 不能为空")
    return errors


class ActionItemExtractor:
    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm

    def extract(self, record_transcripts: list[str]) -> list[ActionItemCandidate]:
        messages = build_extract_action_items({"record_transcripts": record_transcripts})
        result = run_structured(
            lambda msgs: self.llm.chat_json(msgs, schema=ActionItemsResult),
            messages,
            ActionItemsResult,
            scene="extract_action_items",
            validator=_validate_action_items,
        )
        return result.items


class IssueExtractor:
    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm

    def extract(self, record_transcripts: list[str]) -> list[IssueCandidate]:
        messages = build_extract_issues({"record_transcripts": record_transcripts})
        result = run_structured(
            lambda msgs: self.llm.chat_json(msgs, schema=IssuesResult),
            messages,
            IssuesResult,
            scene="extract_issues",
            validator=_validate_issues,
        )
        return result.items
