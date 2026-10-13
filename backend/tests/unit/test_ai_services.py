from __future__ import annotations

from types import SimpleNamespace

from app.ai.chat import ChatService
from app.ai.extraction import (
    ActionItemCandidate,
    ActionItemExtractor,
    ActionItemsResult,
    IssueCandidate,
    IssueExtractor,
    IssuesResult,
)
from app.ai.llm import LLMResult
from app.ai.minutes import MinutesService
from app.ai.preparation import PreparationDraft, PreparationService


class FakeLLM:
    def __init__(self, text: str = "", obj=None) -> None:
        self.text = text
        self.obj = obj

    def chat(self, messages, **kwargs) -> LLMResult:
        return LLMResult(text=self.text, model="m", usage={}, latency_ms=0)

    def chat_json(self, messages, *, schema, **kwargs):
        if self.obj is not None:
            return self.obj
        return schema.model_validate_json(self.text)


class FakeRetriever:
    def __init__(self, chunks) -> None:
        self.chunks = chunks

    def retrieve(self, query, **kwargs):
        return self.chunks


def test_preparation_generate() -> None:
    draft = PreparationDraft(summary="摘要", checklist=["事项"])
    result = PreparationService(FakeLLM(obj=draft)).generate("主题", ["片段"])

    assert result == draft


def test_minutes_generate() -> None:
    result = MinutesService(FakeLLM(text="纪要正文")).generate("主题", ["记录"])

    assert result == "纪要正文"


def test_extract_action_items() -> None:
    result_obj = ActionItemsResult(items=[ActionItemCandidate(content="做某事", assignee="张三")])
    result = ActionItemExtractor(FakeLLM(obj=result_obj)).extract(["记录"])

    assert len(result) == 1
    assert result[0].content == "做某事"
    assert result[0].assignee == "张三"


def test_extract_issues() -> None:
    result_obj = IssuesResult(items=[IssueCandidate(description="未决问题")])
    result = IssueExtractor(FakeLLM(obj=result_obj)).extract(["记录"])

    assert len(result) == 1
    assert result[0].description == "未决问题"


def test_chat_with_sources() -> None:
    chunks = [
        SimpleNamespace(
            meeting_id="meet-1",
            material_id="mat-1",
            record_id=None,
            excerpt="相关资料片段",
        )
    ]
    service = ChatService(FakeLLM(text="答案是：可以"), FakeRetriever(chunks))
    answer = service.answer("可以吗？", user_id="u1", current_meeting_id="meet-1")

    assert answer.insufficient_evidence is False
    assert answer.answer == "答案是：可以"
    assert len(answer.sources) == 1
    assert answer.sources[0].meeting_id == "meet-1"


def test_chat_insufficient_evidence() -> None:
    service = ChatService(FakeLLM(), FakeRetriever([]))
    answer = service.answer("可以吗？", user_id="u1")

    assert answer.insufficient_evidence is True
    assert answer.sources == []
