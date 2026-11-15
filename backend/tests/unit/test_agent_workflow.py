"""Agent 框架单元测试：工作流引擎语义 + 后端意图路由。"""

from __future__ import annotations

import pytest

from app.agent import intent as intent_module
from app.agent.intent import classify
from app.agent.workflow import (
    Edge,
    Step,
    StepRetry,
    WaitForConfirmation,
    Workflow,
    WorkflowRunner,
)
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.schemas.agent import AgentIntent, AgentScene

# ---------------------------------------------------------------- 工作流引擎


def test_condition_edges_and_step_retry() -> None:
    calls = {"flaky": 0, "done": 0}

    def flaky(_context: object, _inputs: dict) -> dict:
        calls["flaky"] += 1
        if calls["flaky"] == 1:
            raise AppError("MODEL_TIMEOUT", "超时")
        return {"ok": True}

    def done(_context: object, _inputs: dict) -> dict:
        calls["done"] += 1
        return {"finished": True}

    workflow = Workflow(
        name="retry",
        entry="a",
        steps={
            "a": Step("a", "flaky", retry=StepRetry(max_attempts=2, backoff_s=(0.0,))),
            "b": Step("b", "done"),
        },
        edges=(
            Edge("a", "b", lambda state: bool(state.get("ok"))),
            Edge("b", None),
        ),
    )
    runner = WorkflowRunner(
        {"flaky": flaky, "done": done}, sleep=lambda _seconds: None
    )
    result = runner.run(workflow)

    assert result.status == "succeeded"
    assert calls == {"flaky": 2, "done": 1}


def test_non_retryable_error_stops_workflow() -> None:
    def boom(_context: object, _inputs: dict) -> dict:
        raise AppError("PERMISSION_DENIED", "无权限")

    workflow = Workflow(
        name="fail",
        entry="a",
        steps={"a": Step("a", "boom", retry=StepRetry(max_attempts=3))},
        edges=(Edge("a", None),),
    )
    result = WorkflowRunner({"boom": boom}).run(workflow)

    assert result.status == "failed"
    assert result.error_code == "PERMISSION_DENIED"


def test_wait_for_confirmation_stops_at_waiting() -> None:
    def ask(_context: object, _inputs: dict) -> dict:
        raise WaitForConfirmation(
            action_type="web_search", question="是否联网？", payload={"q": "x"}
        )

    workflow = Workflow(
        name="confirm",
        entry="ask",
        steps={"ask": Step("ask", "ask")},
        edges=(Edge("ask", None),),
    )
    result = WorkflowRunner({"ask": ask}).run(workflow)

    assert result.status == "waiting"
    assert result.pending_action is not None
    assert result.pending_action.action_type == "web_search"
    assert result.pending_action.payload == {"q": "x"}


def test_step_budget_guard() -> None:
    def again(_context: object, _inputs: dict) -> dict:
        return {}

    workflow = Workflow(
        name="loop",
        entry="a",
        steps={"a": Step("a", "again")},
        edges=(Edge("a", "a"),),
        max_steps=3,
    )
    result = WorkflowRunner({"again": again}).run(workflow)

    assert result.status == "failed"
    assert result.error_code == "AGENT_MAX_STEPS"


# ---------------------------------------------------------------- 意图路由


@pytest.fixture(autouse=True)
def _no_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    """路由单测不发起真实模型调用。"""
    monkeypatch.setattr(intent_module, "_llm_decision", lambda *a, **k: None)


def test_explicit_intent_wins() -> None:
    decision = classify(
        None,  # type: ignore[arg-type] — 显式意图不访问数据库
        user_id="usr_test",
        message="随便说点什么",
        explicit=AgentIntent.organize,
    )
    assert decision.intent is AgentIntent.organize
    assert decision.source == "explicit"
    assert decision.confidence == 1.0


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("请生成会议纪要", AgentIntent.minutes_generate),
        ("帮我提取待办任务", AgentIntent.action_items_extract),
        ("整理一下会议记录", AgentIntent.organize),
        ("生成会前准备清单", AgentIntent.prepare),
        ("帮我做一个会前速览", AgentIntent.brief),
        ("总结一下这份资料", AgentIntent.brief),
        ("查一下我的知识库", AgentIntent.knowledge_search),
        ("联网查最新消息", AgentIntent.web_search),
    ],
)
def test_rule_routing(message: str, expected: AgentIntent) -> None:
    decision = classify(
        None,  # type: ignore[arg-type]
        user_id="usr_test",
        message=message,
        scene=AgentScene.minutes.value,
    )
    assert decision.intent is expected
    assert decision.source == "rule"


def test_ambiguous_message_falls_back_to_chat() -> None:
    decision = classify(
        None,  # type: ignore[arg-type]
        user_id="usr_test",
        message="今天天气不错",
    )
    assert decision.intent is AgentIntent.chat
    assert decision.source == "fallback"


def test_clarify_uses_page_prior() -> None:
    decision = classify(
        None,  # type: ignore[arg-type]
        user_id="usr_test",
        message="帮我处理一下",
        scene=AgentScene.preprocess.value,
    )
    assert decision.intent is AgentIntent.clarify
    assert decision.needs_clarification is True
    assert decision.clarification_question
    assert "会前准备" in decision.clarification_question


# ---------------------------------------------------------------- 预算接线


def test_workflow_budget_follows_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """工作流步数/时长预算来自配置，而不是引擎默认值。"""
    from app.agent.service import _budgeted_workflow

    workflow = _budgeted_workflow("web_fallback")
    assert workflow.max_steps == 20
    assert workflow.max_wall_s == 600.0

    monkeypatch.setattr(get_settings(), "agent_max_steps", 3)
    monkeypatch.setattr(get_settings(), "agent_max_wall_seconds", 12.5)
    budgeted = _budgeted_workflow("web_fallback")
    assert budgeted.max_steps == 3
    assert budgeted.max_wall_s == 12.5
    # 其余定义（步骤、边）不受预算覆盖影响
    assert budgeted.name == workflow.name
    assert budgeted.entry == workflow.entry
    assert budgeted.edges == workflow.edges


def test_workflow_budget_enforced_by_runner() -> None:
    """预算被引擎真正执行：超步数即失败并给出 AGENT_MAX_STEPS。"""
    from app.agent.workflow import WorkflowRunner

    calls = {"a": 0}

    def a(_context: object, _inputs: dict) -> dict:
        calls["a"] += 1
        return {"ok": True}

    workflow = Workflow(
        name="budget",
        entry="a",
        steps={"a": Step("a", "a"), "b": Step("b", "a")},
        edges=(Edge("a", "b"), Edge("b", None)),
        max_steps=1,
    )
    result = WorkflowRunner({"a": a}).run(workflow)

    assert result.status == "failed"
    assert result.error_code == "AGENT_MAX_STEPS"
    assert calls["a"] == 1
