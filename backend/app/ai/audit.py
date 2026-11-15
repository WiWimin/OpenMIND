"""AI 调用审计上下文（`ai-design.md 3.11`）：用量/模型元数据的进程内传递。

`ContextVar` 持有当前请求的可变 `AuditEvent`：服务层用
`ai_audit_service` 建立/清除上下文，`LLMClient` 在调用点把
实际模型、降级来源与 usage 记入事件。上下文不存在时所有 note 为 no-op
（probe、Judge 等未纳入审计的调用不受影响）。

另有任务上下文（`bind_job`/`unbind_job`）：`task_runner.run_job` 绑定
当前 `job_id`，审计预创建时读取以关联 `async_jobs`。

只传数值与枚举标签，不接触提示词或用户内容（日志红线）。
"""

from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from urllib.parse import urlsplit

# 同一请求内的多次 LLM 调用（结构化修复重试、降级切换）累计进同一事件
_current: ContextVar[AuditEvent | None] = ContextVar("ai_audit_event", default=None)


def provider_host(api_base: str) -> str:
    """从 api_base 提取 provider 主机名（审计用，不含路径与凭证）。"""
    return urlsplit(api_base or "").hostname or "unknown"


@dataclass
class AuditEvent:
    """一次被审计调用的元数据；由 LLMClient 与服务层共同填充。"""

    scene: str
    model: str
    provider: str
    transport: str = "sync"
    status: str = "success"
    error_code: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    # 降级链切换的起点模型（未切换为 None）
    fallback_from: str | None = None
    # 降级来源标签（none/global；user/scene/cross_provider 为后续预留）
    fallback_scope: str = "none"
    # 关联 async_jobs.job_id（由 task_runner 绑定；同步调用为 None）
    job_id: str | None = None
    latency_ms: int = 0
    finished: bool = False
    # 纯标签扩展（如 chain_len）；禁止提示词、用户原文与模型输出
    meta: dict[str, str] = field(default_factory=dict)


def begin(event: AuditEvent) -> Token:
    """建立审计上下文，返回用于恢复的 token。"""
    return _current.set(event)


def end(token: Token) -> None:
    """恢复上一层上下文（允许嵌套审计）。

    跨上下文时 token 无法 reset（如 SSE 生成器在 Starlette 的子任务里
    运行，Context 被复制、Token 仍属于原 Context）——此时退回置 None；
    审计上下文不跨任务边界嵌套，语义等价。
    """
    try:
        _current.reset(token)
    except ValueError:
        _current.set(None)


def current() -> AuditEvent | None:
    return _current.get()


# ---------------------------------------------------------------- 任务上下文

# 后台任务执行器绑定的 job_id：审计预创建时读取，用于关联 async_jobs
_job: ContextVar[str | None] = ContextVar("ai_audit_job_id", default=None)


def bind_job(job_id: str) -> Token:
    """绑定当前任务的 job_id（`task_runner.run_job` 调用，返回恢复用 token）。"""
    return _job.set(job_id)


def unbind_job(token: Token) -> None:
    """解除任务绑定（必须与 `bind_job` 同上下文成对调用）。"""
    _job.reset(token)


def current_job_id() -> str | None:
    return _job.get()


def _matches(event: AuditEvent, scene: str | None) -> bool:
    """场景匹配：完全一致，或事件场景是调用场景的前缀（chat → chat_build）。"""
    if scene is None or scene == event.scene:
        return True
    return scene.startswith(f"{event.scene}_")


def note_usage(
    usage: dict[str, int] | None,
    *,
    scene: str | None = None,
    model: str | None = None,
    provider: str | None = None,
) -> None:
    """把一次 LLM 调用的 usage/实际模型/provider 记入当前事件（无上下文则忽略）。"""
    event = _current.get()
    if event is None or not _matches(event, scene):
        return
    if usage:
        event.input_tokens += int(usage.get("input") or 0)
        event.output_tokens += int(usage.get("output") or 0)
    if model:
        event.model = model
    if provider:
        event.provider = provider


def note_fallback(from_model: str, *, scene: str | None = None) -> None:
    """记录降级链切换的起点模型（仅记第一次）。"""
    event = _current.get()
    if event is None or not _matches(event, scene):
        return
    if event.fallback_from is None and from_model:
        event.fallback_from = from_model


def note_chain_len(length: int, *, scene: str | None = None) -> None:
    """记录本次构造的候选链长度（>1 时写入 meta.chain_len）。"""
    event = _current.get()
    if event is None or not _matches(event, scene):
        return
    if length > 1:
        event.meta["chain_len"] = str(length)


def note_error(error_code: str, *, scene: str | None = None) -> None:
    """标记当前事件失败（LLM 层捕获到错误时调用）。"""
    event = _current.get()
    if event is None or not _matches(event, scene):
        return
    event.status = "failed"
    event.error_code = error_code
