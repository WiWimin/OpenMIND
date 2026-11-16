"""轻量工作流引擎：声明式步骤 + 条件边 + 步骤级重试 + 确认门。

不引入 LangGraph（见 `docs/agent-framework.md`）。引擎只做编排：

- `Step` 描述「调用哪个工具、输入如何从状态计算」；
- `Edge.when` 是唯一的分支表达，替代散落的 if-else；
- `StepRetry` 只处理业务步骤的可重试错误；HTTP 传输重试仍在
  `ai/retry.py`，结构化输出修复仍在 `ai/structured.py`，三层职责不重叠；
- `WaitForConfirmation` 让工作流停在 `waiting`，由 `agent_pending_actions`
  记录确认门，用户批准/拒绝后再恢复。

引擎不访问数据库、不写业务表；持久化由调用方通过 `StepRecorder` 完成。
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Literal, Protocol

from app.core.exceptions import AppError

logger = logging.getLogger(__name__)

# 业务步骤默认可重试的错误码（配置/权限/参数错误不重试）
DEFAULT_RETRY_CODES = frozenset(
    {
        "MODEL_TIMEOUT",
        "NETWORK_ERROR",
        "RATE_LIMITED",
        "MODEL_OUTPUT_INVALID",
        "MODEL_QUOTA_EXCEEDED",
        "JOB_TIMEOUT",
    }
)


@dataclass(frozen=True)
class StepRetry:
    """步骤级重试策略：最多 `max_attempts` 次，指数退避。"""

    max_attempts: int = 1
    backoff_s: tuple[float, ...] = (2.0, 5.0)
    retry_on: frozenset[str] = DEFAULT_RETRY_CODES

    def delay(self, attempt: int) -> float:
        if not self.backoff_s:
            return 0.0
        index = min(max(attempt - 1, 0), len(self.backoff_s) - 1)
        return self.backoff_s[index]


@dataclass(frozen=True)
class Step:
    name: str
    tool: str
    input: Callable[[dict], dict] = field(default=lambda _state: {})
    retry: StepRetry = StepRetry()
    # fail=中断工作流；skip=记录后继续；degrade=记录后按默认边继续
    on_error: Literal["fail", "skip", "degrade"] = "fail"
    timeout_s: float | None = None


@dataclass(frozen=True)
class Edge:
    source: str
    # None 表示工作流在此结束
    target: str | None
    # None 表示默认边（仅当没有更早的 when=True 时命中）
    when: Callable[[dict], bool] | None = None


@dataclass(frozen=True)
class Workflow:
    name: str
    entry: str
    steps: Mapping[str, Step]
    edges: tuple[Edge, ...]
    max_steps: int = 20
    max_wall_s: float = 600.0

    def next_step(self, source: str, state: dict) -> str | None:
        """按声明顺序取第一条命中的边；没有命中即结束。"""
        for edge in self.edges:
            if edge.source != source:
                continue
            if edge.when is None or edge.when(state):
                return edge.target
        return None


class WaitForConfirmation(Exception):
    """步骤要求用户确认：工作流转 `waiting`，并登记 pending action。"""

    def __init__(
        self, *, action_type: str, question: str, payload: dict | None = None
    ) -> None:
        self.action_type = action_type
        self.question = question
        self.payload = payload or {}
        super().__init__(question)


class StepRecorder(Protocol):
    def record(
        self,
        *,
        step_name: str,
        status: str,
        attempt: int,
        input: dict | None,
        output: dict | None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> None: ...


@dataclass
class WorkflowResult:
    status: Literal[
        "succeeded", "failed", "waiting", "cancelled"
    ]
    state: dict
    current_step: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    pending_action: WaitForConfirmation | None = None
    steps: int = 0


class WorkflowRunner:
    """同步执行器：适合请求内短工作流与 worker 内的长工作流。"""

    def __init__(
        self,
        tools: Mapping[str, Callable[[object, dict], dict]],
        *,
        recorder: StepRecorder | None = None,
        should_cancel: Callable[[], bool] | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._tools = tools
        self._recorder = recorder
        self._should_cancel = should_cancel or (lambda: False)
        self._sleep = sleep
        self._clock = clock

    def run(
        self,
        workflow: Workflow,
        *,
        state: dict | None = None,
        context: object = None,
    ) -> WorkflowResult:
        data: dict = dict(state or {})
        current = data.get("_next_step") or workflow.entry
        started = self._clock()
        executed = 0

        while current is not None:
            if self._should_cancel():
                return WorkflowResult("cancelled", data, current, steps=executed)
            if executed >= workflow.max_steps:
                return WorkflowResult(
                    "failed",
                    data,
                    current,
                    error_code="AGENT_MAX_STEPS",
                    error_message="工作流步骤数超过上限",
                    steps=executed,
                )
            if self._clock() - started > workflow.max_wall_s:
                return WorkflowResult(
                    "failed",
                    data,
                    current,
                    error_code="AGENT_TIMEOUT",
                    error_message="工作流执行超时",
                    steps=executed,
                )

            step = workflow.steps.get(current)
            if step is None:
                return WorkflowResult(
                    "failed",
                    data,
                    current,
                    error_code="AGENT_STEP_NOT_FOUND",
                    error_message=f"工作流步骤未登记：{current}",
                    steps=executed,
                )

            outcome = self._run_step(step, data, context)
            executed += 1
            if outcome.status == "waiting":
                return WorkflowResult(
                    "waiting",
                    data,
                    current,
                    pending_action=outcome.pending_action,
                    steps=executed,
                )
            if outcome.status == "failed":
                return WorkflowResult(
                    "failed",
                    data,
                    current,
                    error_code=outcome.error_code,
                    error_message=outcome.error_message,
                    steps=executed,
                )

            data.update(outcome.output)
            next_step = workflow.next_step(step.name, data)
            if next_step is None:
                return WorkflowResult("succeeded", data, step.name, steps=executed)
            data["_next_step"] = next_step
            current = next_step

        return WorkflowResult("succeeded", data, None, steps=executed)

    def _run_step(
        self, step: Step, state: dict, context: object
    ) -> _StepOutcome:
        tool = self._tools.get(step.tool)
        if tool is None:
            return _StepOutcome(
                "failed",
                error_code="AGENT_TOOL_NOT_FOUND",
                error_message=f"工具未登记：{step.tool}",
            )

        attempt = 0
        while True:
            attempt += 1
            inputs = step.input(state)
            try:
                output = tool(context, inputs)
            except WaitForConfirmation as waiting:
                self._record(
                    step,
                    status="waiting",
                    attempt=attempt,
                    inputs=inputs,
                    output=None,
                )
                return _StepOutcome("waiting", pending_action=waiting)
            except AppError as exc:
                if (
                    attempt < step.retry.max_attempts
                    and exc.error_code in step.retry.retry_on
                ):
                    self._record(
                        step,
                        status="retrying",
                        attempt=attempt,
                        inputs=inputs,
                        output=None,
                        error_code=exc.error_code,
                        error_message=exc.message,
                    )
                    self._sleep(step.retry.delay(attempt))
                    continue
                self._record(
                    step,
                    status="failed",
                    attempt=attempt,
                    inputs=inputs,
                    output=None,
                    error_code=exc.error_code,
                    error_message=exc.message,
                )
                if step.on_error in ("skip", "degrade"):
                    logger.warning(
                        "工作流步骤失败按 %s 继续 workflow=%s step=%s code=%s",
                        step.on_error,
                        step.tool,
                        step.name,
                        exc.error_code,
                    )
                    return _StepOutcome(
                        "ok",
                        output={
                            "step_error": {
                                "code": exc.error_code,
                                "message": exc.message,
                            }
                        },
                    )
                return _StepOutcome(
                    "failed", error_code=exc.error_code, error_message=exc.message
                )
            except Exception as exc:  # noqa: BLE001 — 未知异常统一归一
                logger.exception("工作流步骤异常 step=%s", step.name)
                self._record(
                    step,
                    status="failed",
                    attempt=attempt,
                    inputs=inputs,
                    output=None,
                    error_code="INTERNAL_ERROR",
                    error_message=type(exc).__name__,
                )
                if step.on_error in ("skip", "degrade"):
                    return _StepOutcome("ok", output={"step_error": {"code": "INTERNAL_ERROR"}})
                return _StepOutcome(
                    "failed",
                    error_code="INTERNAL_ERROR",
                    error_message="工作流步骤执行失败",
                )

            self._record(
                step, status="succeeded", attempt=attempt, inputs=inputs, output=output
            )
            return _StepOutcome("ok", output=output or {})

    def _record(
        self,
        step: Step,
        *,
        status: str,
        attempt: int,
        inputs: dict | None,
        output: dict | None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> None:
        if self._recorder is None:
            return
        try:
            self._recorder.record(
                step_name=step.name,
                status=status,
                attempt=attempt,
                input=inputs,
                output=output,
                error_code=error_code,
                error_message=error_message,
            )
        except Exception:  # noqa: BLE001 — 轨迹写入失败不影响主流程
            logger.exception("工作流步骤轨迹写入失败 step=%s", step.name)


@dataclass
class _StepOutcome:
    status: Literal["ok", "failed", "waiting"]
    output: dict = field(default_factory=dict)
    error_code: str | None = None
    error_message: str | None = None
    pending_action: WaitForConfirmation | None = None
