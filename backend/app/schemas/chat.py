from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field, RootModel


class ChatContextScope(StrEnum):
    current_meeting = "current_meeting"
    current_and_history = "current_and_history"
    knowledge_base = "knowledge_base"


class ChatRequest(BaseModel):
    question: str = Field(min_length=1)
    context_scope: ChatContextScope = ChatContextScope.current_meeting
    include_sources: bool = True
    # 可选：覆盖本次对话使用的模型名，必须已在模型配置中登记
    model: str | None = Field(default=None, max_length=100)
    # 对话模式：plan=先讨论规划；build=基于资料直接产出可交付文件（附件）
    mode: Literal["plan", "build"] = "plan"


class ChatFile(BaseModel):
    """Build 模式产出的可交付文件（Markdown 正文，由前端转 DOCX 下载/上传/镜像）。"""

    filename: str
    content: str


class ChatSource(BaseModel):
    meeting_id: str | None
    material_id: str | None
    record_id: str | None
    document_id: str | None = None
    document_name: str | None = None
    excerpt: str
    # 来源类别：material（材料/知识库）| record（会议记录）| web（联网检索）
    origin: str = "material"
    url: str | None = None
    title: str | None = None


class ChatResponse(BaseModel):
    answer: str
    sources: list[ChatSource]
    insufficient_evidence: bool
    # Build 模式产出（plan 模式或无证据时为 null）
    file: ChatFile | None = None


class OrganizeTask(StrEnum):
    organize = "organize"  # 整理记录（正文输出）
    summary = "summary"  # 提炼要点（JSON：结论/讨论/待办/待确认）
    brief = "brief"  # 简短摘要（正文输出）
    polish = "polish"  # 修正口误（JSON diff 建议）


class SummaryKeyDiscussion(BaseModel):
    topic: str = Field(min_length=1)
    points: list[str] = Field(default_factory=list)


class SummaryActionItem(BaseModel):
    task: str = Field(min_length=1)
    assignee: str | None = None
    deadline: str | None = None
    # 提示词固定输出 high/medium/low；缺字段由 schema 拦截并进入修复重试
    priority: str
    # 非法取值（非 high/medium/low）由业务校验拦截
    source_quote: str | None = None


class SummaryStructured(BaseModel):
    """summary 任务的结构化输出契约（对齐前端 `types/chat.ts SummaryStructured`）。"""

    conclusion: list[str] = Field(default_factory=list)
    key_discussions: list[SummaryKeyDiscussion] = Field(default_factory=list)
    action_items: list[SummaryActionItem] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)


class PolishSuggestion(BaseModel):
    """polish 单条修改建议（对齐前端 `types/chat.ts PolishSuggestion`）。"""

    location: str
    original: str
    suggested: str
    reason: str
    confidence: str


class PolishSuggestions(RootModel[list[PolishSuggestion]]):
    """polish 任务的结构化输出契约（JSON 数组根）。"""


class OrganizeRequest(BaseModel):
    # 输入源三级回退：text > audio_id > record_ids（空 = 最近 20 条 ≤8000 字记录）
    record_ids: list[str] = Field(default_factory=list)
    task: OrganizeTask = OrganizeTask.organize
    style: str = Field(default="", max_length=200)
    text: str = Field(default="", max_length=20000)
    # 用户附加要求：随任务注入设计好的提示词（快捷任务标记 + 用户补充文字场景）
    instruction: str = Field(default="", max_length=2000)
    audio_id: str | None = Field(default=None, max_length=40)
    # 可选：覆盖本次任务使用的模型名，必须已在模型配置中登记
    model: str | None = Field(default=None, max_length=100)


class OrganizeResponse(BaseModel):
    task: OrganizeTask
    organized_content: str
    # summary/polish 任务的服务端解析结果；解析失败为 null（此时 organized_content 为原始输出）
    structured: dict[str, Any] | list[Any] | None = None
    source_record_ids: list[str]
