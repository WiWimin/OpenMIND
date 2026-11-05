from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services import memory_service


def _memory(**fields: str | None) -> SimpleNamespace:
    base = {
        "role": None,
        "work_scenarios": None,
        "communication_style": None,
        "preferred_minutes_template": None,
    }
    base.update(fields)
    return SimpleNamespace(**base)


@pytest.fixture()
def fake_memory(monkeypatch: pytest.MonkeyPatch):
    def _install(memory: SimpleNamespace) -> None:
        monkeypatch.setattr(memory_service, "get_memory", lambda db, user_id: memory)

    return _install


def test_context_empty_without_memory(fake_memory) -> None:
    fake_memory(None)
    assert memory_service.memory_context_for(None, "usr_1", "preparation") == ""


def test_context_short_values_not_truncated(fake_memory) -> None:
    fake_memory(
        _memory(
            role="产品经理",
            work_scenarios="B2B SaaS",
            communication_style="结论先行",
        )
    )
    text = memory_service.memory_context_for(None, "usr_1", "preparation")

    assert "用户角色：产品经理" in text
    assert "工作场景：B2B SaaS" in text
    assert "表达偏好：结论先行" in text
    assert "…" not in text


def test_context_total_length_capped_at_500(fake_memory) -> None:
    fake_memory(
        _memory(
            role="角色" * 50,
            work_scenarios="场景" * 500,
            communication_style="风格" * 500,
        )
    )
    text = memory_service.memory_context_for(None, "usr_1", "preparation")

    assert len(text) <= 500
    assert "…" in text


def test_context_drops_later_fields_when_over_limit(fake_memory) -> None:
    """超限时当前字段截断并加省略号，后续字段整体丢弃，保持语义完整。"""
    fake_memory(
        _memory(
            role="产品经理" * 40,
            work_scenarios="场景内容" * 400,
            communication_style="表达偏好值",
        )
    )
    text = memory_service.memory_context_for(None, "usr_1", "preparation")

    assert len(text) <= 500
    assert text.endswith("…")
    assert "表达偏好" not in text


def test_context_minutes_purpose_only_style(fake_memory) -> None:
    fake_memory(
        _memory(role="角色", work_scenarios="场景", communication_style="结论先行" * 200)
    )
    text = memory_service.memory_context_for(None, "usr_1", "minutes")

    assert text.startswith("表达偏好：")
    assert "用户角色" not in text
    assert "工作场景" not in text
    assert len(text) <= 500


def test_context_prepends_lines_within_limit(fake_memory) -> None:
    """正好在上限内的多字段组合不被截断。"""
    fake_memory(
        _memory(role="角色", work_scenarios="场" * 100, communication_style="风格" * 100)
    )
    text = memory_service.memory_context_for(None, "usr_1", "preparation")

    assert "…" not in text
    assert len(text) <= 500
    assert "表达偏好" in text
