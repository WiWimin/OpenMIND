from __future__ import annotations

from app.ai.prompts import (
    build_chat,
    build_extract_action_items,
    build_extract_issues,
    build_minutes,
    build_organize,
    build_prepare,
)

CONTEXT = {
    "meeting_topic": "Q3 产品规划",
    "material_snippets": ["片段A", "片段B"],
    "record_transcripts": ["记录1", "记录2"],
    "question": "本次会议结论是什么？",
    "contexts": ["上下文1", "上下文2"],
}


def _assert_messages(messages: list[dict[str, str]]) -> None:
    assert len(messages) >= 2
    assert messages[0]["role"] == "system"
    assert messages[-1]["role"] == "user"
    for message in messages:
        assert isinstance(message["content"], str)
        assert message["content"].strip()


def test_build_prepare() -> None:
    messages = build_prepare(CONTEXT)
    _assert_messages(messages)
    assert "Q3 产品规划" in messages[-1]["content"]
    assert "片段A" in messages[-1]["content"]


def test_build_minutes() -> None:
    messages = build_minutes(CONTEXT)
    _assert_messages(messages)
    assert "记录1" in messages[-1]["content"]


def test_build_extract_action_items() -> None:
    messages = build_extract_action_items(CONTEXT)
    _assert_messages(messages)
    assert "记录2" in messages[-1]["content"]


def test_build_extract_issues() -> None:
    messages = build_extract_issues(CONTEXT)
    _assert_messages(messages)
    assert "记录1" in messages[-1]["content"]


def test_build_chat() -> None:
    messages = build_chat(CONTEXT)
    _assert_messages(messages)
    assert "本次会议结论是什么" in messages[-1]["content"]
    assert "上下文1" in messages[-1]["content"]


def test_build_organize() -> None:
    messages = build_organize(CONTEXT)
    _assert_messages(messages)
    assert "记录2" in messages[-1]["content"]
