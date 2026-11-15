from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.chat import ChatFile, ChatSource


class AgentIntent(StrEnum):
    chat = "chat"
    brief = "brief"
    prepare = "prepare"
    organize = "organize"
    minutes_generate = "minutes_generate"
    action_items_extract = "action_items_extract"
    issues_extract = "issues_extract"
    knowledge_search = "knowledge_search"
    build_file = "build_file"
    web_search = "web_search"
    transcribe = "transcribe"
    clarify = "clarify"
    help = "help"


class AgentScene(StrEnum):
    preprocess = "preprocess"
    asr = "asr"
    minutes = "minutes"


class AgentSessionStatus(StrEnum):
    active = "active"
    archived = "archived"


class AgentRunStatus(StrEnum):
    pending = "pending"
    running = "running"
    waiting = "waiting"
    succeeded = "succeeded"
    failed = "failed"
    cancelled = "cancelled"


class AgentPendingActionStatus(StrEnum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    expired = "expired"


class AgentIntentRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    scene: AgentScene = AgentScene.minutes
    meeting_id: str | None = Field(default=None, max_length=40)
    # 显式覆盖（快捷卡）：非空时直接采用，不做分类
    intent: AgentIntent | None = None


class AgentIntentDecision(BaseModel):
    intent: AgentIntent
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    slots: dict[str, str] = Field(default_factory=dict)
    needs_clarification: bool = False
    clarification_question: str | None = None
    source: Literal["explicit", "rule", "llm", "fallback"] = "rule"


class AgentTurnOptions(BaseModel):
    """页面透传的执行选项（模型/模板/对话模式/引用上下文）。"""

    model: str | None = Field(default=None, max_length=100)
    mode: Literal["plan", "build"] = "plan"
    # 简单文本任务（润色/精简/改写/翻译）：走公共 prompt_task，不落库
    quick_task: Literal["polish", "condense", "rewrite", "translate"] | None = None
    template: str | None = Field(default=None, max_length=40)
    template_id: str | None = Field(default=None, max_length=40)
    context_scope: str = Field(default="current_meeting", max_length=40)
    include_sources: bool = True
    include_history: bool = True
    include_action_items: bool = False
    include_materials: bool = True
    user_goal: str | None = Field(default=None, max_length=4000)
    context: str | None = Field(default=None, max_length=8000)
    # 是否请求模型思考模式（推理链）；关闭后不下发 reasoning 事件
    thinking: bool = True


class AgentTurnRequest(BaseModel):
    # 省略时按「user + scene + meeting」查找或创建默认会话
    session_id: str | None = Field(default=None, max_length=40)
    meeting_id: str | None = Field(default=None, max_length=40)
    scene: AgentScene = AgentScene.minutes
    message: str = Field(default="", max_length=8000)
    # 显式意图（快捷卡）；空时由后端路由
    intent: AgentIntent | None = None
    options: AgentTurnOptions = Field(default_factory=AgentTurnOptions)


class AgentSessionCreate(BaseModel):
    meeting_id: str | None = Field(default=None, max_length=40)
    scene: AgentScene = AgentScene.minutes
    title: str | None = Field(default=None, max_length=200)


class AgentSessionUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    status: AgentSessionStatus | None = None


class AgentSessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    session_id: str
    user_id: str
    meeting_id: str | None = None
    scene: str
    title: str | None = None
    status: str
    meta: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime
    last_message_at: datetime | None = None


class AgentMessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    message_id: str
    session_id: str
    role: str
    content: str
    kind: str | None = None
    structured: Any | None = None
    sources: list[Any] | None = None
    file: dict[str, Any] | None = None
    status: str
    job_id: str | None = None
    meta: dict[str, Any] | None = None
    created_at: datetime


class AgentPendingActionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    action_id: str
    session_id: str
    run_id: str | None = None
    action_type: str
    question: str
    payload: dict[str, Any] | None = None
    status: str
    expires_at: datetime | None = None
    created_at: datetime
    decided_at: datetime | None = None


class AgentRunStepRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    step_id: str
    run_id: str
    step_name: str
    status: str
    attempt: int
    input: dict[str, Any] | None = None
    output: dict[str, Any] | None = None
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime
    finished_at: datetime | None = None


class AgentRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run_id: str
    session_id: str
    user_id: str
    meeting_id: str | None = None
    workflow: str
    status: str
    current_step: str | None = None
    state: dict[str, Any] | None = None
    job_id: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class AgentReply(BaseModel):
    """助手回复（与前端 AgentReply 对齐）。"""

    content: str = ""
    kind: str | None = None
    structured: Any | None = None
    sources: list[ChatSource] = Field(default_factory=list)
    note: str | None = None
    file: ChatFile | None = None
    # 意图相关的业务结果（纪要/准备稿/行动项等），供页面刷新局部状态
    result: Any | None = None
    # 思考过程（推理链）：仅问答类流式产出；原生推理文本 + 真实执行步骤
    reasoning: str | None = None
    reasoning_ms: int | None = None
    trace: list[dict[str, Any]] | None = None


class AgentTurnResponse(BaseModel):
    session_id: str
    intent: AgentIntentDecision
    user_message: AgentMessageRead | None = None
    assistant_message: AgentMessageRead | None = None
    pending_action: AgentPendingActionRead | None = None
    run: AgentRunRead | None = None
    # 需要异步完成（202 语义）时为 true
    accepted: bool = False


class AgentPendingActionDecision(BaseModel):
    """批准/拒绝载荷：可附带补充要求。"""

    note: str | None = Field(default=None, max_length=2000)


class AgentSessionDeleteResult(BaseModel):
    deleted: bool = True
    session_id: str
