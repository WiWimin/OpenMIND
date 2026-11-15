from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field, RootModel, model_validator


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
    # 是否请求模型思考模式（推理链）；关闭后前端不展示思考过程
    thinking: bool = True


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


def _clip_text(text: str, limit: int) -> str:
    value = (text or "").strip()
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "…"


def _clean_items(items: list[str], *, max_items: int, max_chars: int) -> list[str]:
    cleaned = [_clip_text(item, max_chars) for item in items if (item or "").strip()]
    return cleaned[:max_items]


class MaterialBrief(BaseModel):
    """会前速览结构化契约（对齐前端 `types/chat.ts MaterialBrief`）。

    长度约束在 `model_validator` 内做**确定性收口**：模型偶尔超长时截断而不是
    报错重试，保证摘要卡始终可渲染；提示词仍负责“尽量一次写对”。
    """

    headline: str = Field(min_length=1)
    key_points: list[str] = Field(default_factory=list)
    decisions_needed: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    next_step: str = ""

    @model_validator(mode="after")
    def _normalize(self) -> MaterialBrief:
        self.headline = _clip_text(self.headline, 40)
        self.key_points = _clean_items(self.key_points, max_items=5, max_chars=40)
        self.decisions_needed = _clean_items(
            self.decisions_needed, max_items=3, max_chars=30
        )
        self.risks = _clean_items(self.risks, max_items=2, max_chars=30)
        self.next_step = _clip_text(self.next_step, 40)

        # 总字数兜底（确定性收口，保证 ≤300）：
        # 1) 优先保留前 3 条要点；2) 压缩一句话与下一步；
        # 3) 仍超限时按 需确认 → 风险 → 要点 的顺序裁剪，最后再压到最短。
        while self._total_chars() > 300 and len(self.key_points) > 3:
            self.key_points.pop()
        if self._total_chars() > 300:
            self.headline = _clip_text(self.headline, 28)
            self.next_step = _clip_text(self.next_step, 24)
        while self._total_chars() > 300 and self.decisions_needed:
            self.decisions_needed.pop()
        while self._total_chars() > 300 and self.risks:
            self.risks.pop()
        while self._total_chars() > 300 and len(self.key_points) > 1:
            self.key_points.pop()
        if self._total_chars() > 300:
            self.headline = _clip_text(self.headline, 20)
            self.next_step = _clip_text(self.next_step, 20)
        return self

    def _total_chars(self) -> int:
        return (
            len(self.headline)
            + sum(len(item) for item in self.key_points)
            + sum(len(item) for item in self.decisions_needed)
            + sum(len(item) for item in self.risks)
            + len(self.next_step)
        )


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
