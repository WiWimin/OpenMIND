from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.ai.chat import ChatService, RecordContext, Source
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
from app.ai.prompts.minutes import build_minutes


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


def test_minutes_prompt_includes_materials_records_and_markers() -> None:
    messages = build_minutes(
        {
            "meeting_topic": "周会",
            "record_transcripts": ["讨论上线时间"],
            "material_snippets": ["项目计划：周五上线"],
            "marked_records": [
                {
                    "record_id": "rec_1",
                    "marker_type": "decision",
                    "content": "决定周五上线",
                }
            ],
        }
    )

    system = messages[0]["content"]
    user = messages[1]["content"]
    assert "会议资料" in system
    assert "项目计划：周五上线" in user
    assert "讨论上线时间" in user
    assert "[决议] 决定周五上线" in user


def test_minutes_prompt_uses_concise_template() -> None:
    messages = build_minutes(
        {
            "meeting_topic": "周会",
            "record_transcripts": ["讨论上线时间"],
            "material_snippets": [],
            "marked_records": [],
            "template": "concise",
        }
    )

    assert "简洁" in messages[0]["content"]


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


def test_chat_maps_knowledge_source() -> None:
    chunks = [
        SimpleNamespace(
            meeting_id=None,
            material_id=None,
            record_id=None,
            document_id="kdoc_1",
            document_name="notes.txt",
            excerpt="知识库片段",
        )
    ]
    service = ChatService(FakeLLM(text="根据知识库回答"), FakeRetriever(chunks))
    answer = service.answer("问题", user_id="u1", scope="knowledge_base")

    assert answer.insufficient_evidence is False
    assert answer.sources[0].document_id == "kdoc_1"
    assert answer.sources[0].document_name == "notes.txt"
    assert answer.sources[0].meeting_id is None


def test_chat_insufficient_evidence() -> None:
    service = ChatService(FakeLLM(), FakeRetriever([]))
    answer = service.answer("可以吗？", user_id="u1")

    assert answer.insufficient_evidence is True
    assert answer.sources == []


def test_chat_web_fallback_when_no_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    """两段式联网补救：先告知资料无证据，再基于联网片段作答。"""
    from app.ai.chat import service as chat_service_module
    from app.ai.websearch import WebResult

    monkeypatch.setattr(
        chat_service_module,
        "web_search",
        lambda query: [
            WebResult(
                title="权威页面",
                url="https://example.com/a",
                snippet="这是联网检索到的片段",
            )
        ],
    )
    service = ChatService(FakeLLM(text="联网回答正文"), FakeRetriever([]))
    answer = service.answer("有人知道吗？", user_id="u1")

    assert answer.insufficient_evidence is True
    assert answer.answer.startswith("你的会议资料中未找到相关证据")
    assert "联网回答正文" in answer.answer
    assert len(answer.sources) == 1
    assert answer.sources[0].origin == "web"
    assert answer.sources[0].url == "https://example.com/a"
    assert answer.sources[0].title == "权威页面"


def test_chat_web_no_results_keeps_refusal(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.ai.chat import service as chat_service_module

    monkeypatch.setattr(chat_service_module, "web_search", lambda query: [])
    service = ChatService(FakeLLM(), FakeRetriever([]))
    answer = service.answer("有人知道吗？", user_id="u1")

    assert answer.insufficient_evidence is True
    assert answer.answer == "根据现有材料无法确认该问题的答案。"
    assert answer.sources == []


def test_chat_web_llm_failure_falls_back_to_refusal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """联网命中但 LLM 不可用（未配置/超时）→ 回退拒答，不裸报错。"""
    from app.ai.chat import service as chat_service_module
    from app.ai.websearch import WebResult
    from app.core.exceptions import AppError

    monkeypatch.setattr(
        chat_service_module,
        "web_search",
        lambda query: [WebResult(title="t", url="https://e.com", snippet="s")],
    )

    class BoomLLM:
        def chat(self, messages):  # noqa: ANN001
            raise AppError(
                "MODEL_CONFIG_REQUIRED", "未配置大模型（LLM）", http_status=400
            )

    service = ChatService(BoomLLM(), FakeRetriever([]))  # type: ignore[arg-type]
    answer = service.answer("有人知道吗？", user_id="u1")

    assert answer.answer == "根据现有材料无法确认该问题的答案。"
    assert answer.sources == []
    assert answer.insufficient_evidence is True


def test_chat_build_mode_produces_file() -> None:
    """Build 模式：基于资料产出结构化文件，summary 作为回答。"""

    chunks = [
        SimpleNamespace(
            meeting_id="meet-1",
            material_id="mat-1",
            record_id=None,
            excerpt="Q3 预算：市场投放 120 万。",
        )
    ]

    class BuildLLM:
        def chat_json(self, messages, *, schema, **kwargs):  # noqa: ANN001, ANN003
            assert "可交付文件" in messages[0]["content"]
            return schema.model_validate(
                {
                    "summary": "已生成 Q3 预算清单文件。",
                    "filename": "q3-budget.md",
                    "content_md": "# Q3 预算\n\n- 市场投放 120 万",
                }
            )

    service = ChatService(BuildLLM(), FakeRetriever(chunks))  # type: ignore[arg-type]
    answer = service.answer("生成预算清单", user_id="u1", mode="build")

    assert answer.file is not None
    assert answer.file.filename == "q3-budget.md"
    assert "市场投放 120 万" in answer.file.content_md
    assert answer.answer == "已生成 Q3 预算清单文件。"
    assert answer.insufficient_evidence is False


def test_chat_plan_mode_has_no_file() -> None:
    chunks = [
        SimpleNamespace(
            meeting_id="meet-1",
            material_id="mat-1",
            record_id=None,
            excerpt="相关内容",
        )
    ]
    service = ChatService(FakeLLM(text="普通回答"), FakeRetriever(chunks))
    answer = service.answer("问题", user_id="u1", mode="plan")

    assert answer.file is None
    assert answer.answer == "普通回答"


def test_chat_uses_limited_record_context_with_source() -> None:
    service = ChatService(FakeLLM(text="根据记录回答"), FakeRetriever([]))
    answer = service.answer(
        "决定了什么？",
        user_id="u1",
        current_meeting_id="meet-1",
        records=[
            RecordContext(
                meeting_id="meet-1",
                record_id="rec_1",
                content="决定周五前完成联调",
            )
        ],
    )

    assert answer.insufficient_evidence is False
    assert answer.sources == [
        Source(
            meeting_id="meet-1",
            material_id=None,
            record_id="rec_1",
            excerpt="决定周五前完成联调",
        )
    ]
