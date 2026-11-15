"""会前速览服务：只读本场会议资料，生成 `MaterialBrief` 摘要卡。

与 `preparation_service` 的区别：

- 本服务只读**当前会议**资料（6 份 / 12000 字上限），不读用户历史资料；
- 不落库、不产文件、不覆盖原文，结果仅作为一次对话回复返回；
- 输出为结构化摘要卡（`kind="brief"`），由前端 `BriefCard` 渲染。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.ai import audit
from app.ai.brief import BriefMaterial, MaterialBriefService
from app.repositories import material_repository
from app.schemas.chat import ChatSource, MaterialBrief
from app.services import ai_audit_service, meeting_service
from app.services.model_config_service import (
    ModelPurpose,
    build_llm_client,
    resolve_model_config,
)

# 单场资料上限：保证会前速览在 60 秒内可读，同时控制 token 成本
MAX_MATERIALS = 6
MAX_TOTAL_CHARS = 12000
MAX_PER_MATERIAL_CHARS = 3000
# 来源片段展示长度（前端折叠展示，不参与模型输入）
SOURCE_EXCERPT_CHARS = 160


@dataclass
class BriefOutcome:
    brief: MaterialBrief | None
    sources: list[ChatSource] = field(default_factory=list)
    material_count: int = 0

    @property
    def empty(self) -> bool:
        return self.material_count == 0


def _load_materials(
    db: Session, meeting_id: str
) -> tuple[list[BriefMaterial], list[ChatSource]]:
    rows = material_repository.list_by_meeting(
        db, meeting_id, limit=MAX_MATERIALS, offset=0
    )
    # 按创建时间正序输入，便于模型按资料顺序理解上下文
    rows = list(reversed(rows))
    materials: list[BriefMaterial] = []
    sources: list[ChatSource] = []
    used = 0
    for row in rows:
        content = (row.content or "").strip()
        if not content:
            continue
        remaining = MAX_TOTAL_CHARS - used
        if remaining <= 0:
            break
        clipped = content[: min(MAX_PER_MATERIAL_CHARS, remaining)]
        used += len(clipped)
        materials.append(
            BriefMaterial(material_id=row.material_id, name=row.file_name, content=clipped)
        )
        sources.append(
            ChatSource(
                meeting_id=meeting_id,
                material_id=row.material_id,
                record_id=None,
                document_name=row.file_name,
                excerpt=clipped[:SOURCE_EXCERPT_CHARS],
                origin="material",
                title=row.file_name,
            )
        )
    return materials, sources


def generate_brief(
    db: Session,
    *,
    meeting_id: str,
    user_id: str,
    user_goal: str | None = None,
    model: str | None = None,
) -> BriefOutcome:
    meeting = meeting_service.get_owned_meeting(db, meeting_id, user_id)
    materials, sources = _load_materials(db, meeting_id)
    if not materials:
        return BriefOutcome(brief=None, material_count=0)

    config = resolve_model_config(
        db, user_id, purpose=ModelPurpose.chat, model_override=model
    )
    topic_parts = [meeting.title]
    if meeting.topic:
        topic_parts.append(meeting.topic)
    service = MaterialBriefService(build_llm_client(config))
    with ai_audit_service.audit_call(
        db,
        user_id=user_id,
        scene="brief",
        model=getattr(config, "llm_model", "") or "",
        provider=audit.provider_host(getattr(config, "llm_api_base", "") or ""),
    ):
        brief = service.generate(
            meeting_topic=" / ".join(part for part in topic_parts if part),
            materials=materials,
            user_goal=(user_goal or "").strip(),
        )
    return BriefOutcome(brief=brief, sources=sources, material_count=len(materials))


def render_brief_text(outcome: BriefOutcome) -> str:
    """把摘要卡渲染成对话正文（SSE/纯文本客户端可读，卡片负责视觉）。"""
    brief = outcome.brief
    if brief is None:
        return "本场会议还没有可用资料。"
    lines: list[str] = ["## 会前速览", brief.headline]
    if brief.key_points:
        lines.append("")
        lines.extend(f"- {item}" for item in brief.key_points)
    if brief.decisions_needed:
        lines.append("")
        lines.append("**需会上确认**")
        lines.extend(f"- {item}" for item in brief.decisions_needed)
    if brief.risks:
        lines.append("")
        lines.append("**风险**")
        lines.extend(f"- {item}" for item in brief.risks)
    if brief.next_step:
        lines.append("")
        lines.append(f"**下一步**：{brief.next_step}")
    return "\n".join(lines)
