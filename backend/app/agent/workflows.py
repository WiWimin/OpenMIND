"""工作流定义：条件边集中声明，替代散落的 if-else。

当前包含两条 MVP 工作流（`docs/agent-framework.md 3.2`）：

- `web_fallback`：资料无证据 → 先请求确认 → 批准才联网 → 回答/拒答；
- `transcribe_to_minutes`：转写 → 确认门 → 生成 draft 纪要 → 可选行动项。
"""

from __future__ import annotations

from app.agent.workflow import Edge, Step, StepRetry, Workflow

WEB_FALLBACK = Workflow(
    name="web_fallback",
    entry="retrieve",
    steps={
        "retrieve": Step("retrieve", "retrieve"),
        "answer_from_context": Step("answer_from_context", "answer_from_context"),
        "ask_web_permission": Step(
            "ask_web_permission", "ask_web_permission", retry=StepRetry(max_attempts=1)
        ),
        "web_search": Step(
            "web_search",
            "web_search",
            retry=StepRetry(max_attempts=2, backoff_s=(2.0,)),
            on_error="skip",
        ),
        "answer_with_web": Step(
            "answer_with_web",
            "answer_with_web",
            retry=StepRetry(max_attempts=2, backoff_s=(2.0,)),
        ),
        "refuse": Step("refuse", "refuse"),
    },
    edges=(
        Edge("retrieve", "answer_from_context", lambda s: bool(s.get("has_evidence"))),
        Edge(
            "retrieve",
            "ask_web_permission",
            lambda s: not s.get("has_evidence") and s.get("require_confirmation", True),
        ),
        Edge(
            "retrieve",
            "web_search",
            lambda s: not s.get("has_evidence") and not s.get("require_confirmation", True),
        ),
        Edge("ask_web_permission", "web_search", lambda s: bool(s.get("approved"))),
        Edge("ask_web_permission", "refuse", lambda s: not s.get("approved")),
        Edge("web_search", "answer_with_web", lambda s: bool(s.get("has_web"))),
        Edge("web_search", "refuse", lambda s: not s.get("has_web")),
        Edge("answer_from_context", None),
        Edge("answer_with_web", None),
        Edge("refuse", None),
    ),
)


TRANSCRIBE_TO_MINUTES = Workflow(
    name="transcribe_to_minutes",
    entry="load_audio",
    steps={
        "load_audio": Step("load_audio", "load_audio"),
        "transcribe_audio": Step(
            "transcribe_audio",
            "transcribe_audio",
            retry=StepRetry(max_attempts=2, backoff_s=(3.0,)),
        ),
        "require_transcript_confirmation": Step(
            "require_transcript_confirmation", "require_transcript_confirmation"
        ),
        "generate_minutes_draft": Step(
            "generate_minutes_draft",
            "generate_minutes_draft",
            retry=StepRetry(max_attempts=2, backoff_s=(2.0, 5.0)),
        ),
        "extract_action_items": Step(
            "extract_action_items",
            "extract_action_items",
            retry=StepRetry(max_attempts=1),
            on_error="skip",
        ),
        "notify": Step("notify", "notify"),
    },
    edges=(
        Edge(
            "load_audio",
            "transcribe_audio",
            lambda s: not (s.get("transcript") or "").strip(),
        ),
        Edge(
            "load_audio",
            "require_transcript_confirmation",
            lambda s: bool((s.get("transcript") or "").strip()),
        ),
        Edge("transcribe_audio", "require_transcript_confirmation"),
        Edge("require_transcript_confirmation", "generate_minutes_draft"),
        Edge(
            "generate_minutes_draft",
            "extract_action_items",
            lambda s: bool(s.get("include_action_items")),
        ),
        Edge("generate_minutes_draft", "notify"),
        Edge("extract_action_items", "notify"),
        Edge("notify", None),
    ),
)


WORKFLOWS: dict[str, Workflow] = {
    WEB_FALLBACK.name: WEB_FALLBACK,
    TRANSCRIBE_TO_MINUTES.name: TRANSCRIBE_TO_MINUTES,
}


def get_workflow(name: str) -> Workflow:
    workflow = WORKFLOWS.get(name)
    if workflow is None:
        raise KeyError(f"工作流未登记：{name}")
    return workflow
