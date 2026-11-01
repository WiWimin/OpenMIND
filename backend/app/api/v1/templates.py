from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, Form, UploadFile, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.common import Envelope
from app.schemas.meeting_template import (
    MeetingTemplateDeleteResult,
    MeetingTemplateDetailRead,
    MeetingTemplateRead,
    TemplateGenerateDraft,
    TemplateGenerateRequest,
    TemplateSource,
    TemplateTextCreate,
)
from app.services import meeting_template_service

router = APIRouter(tags=["meeting-templates"])


def _custom_read(template: object) -> MeetingTemplateRead:
    return MeetingTemplateRead(
        template_id=template.template_id,
        name=template.name,
        description=template.description,
        category=template.category,
        source=TemplateSource.custom,
        file_name=template.file_name,
        created_at=template.created_at,
        content_preview=template.content_text[:60],
    )


@router.get("/meeting-templates", response_model=Envelope[list[MeetingTemplateRead]])
def list_templates(db: DbSession, current_user: CurrentUser) -> Envelope[list[MeetingTemplateRead]]:
    items = meeting_template_service.list_templates(db, current_user.user_id)
    return Envelope(data=[MeetingTemplateRead.model_validate(item) for item in items])


@router.post(
    "/meeting-templates",
    status_code=status.HTTP_201_CREATED,
    response_model=Envelope[MeetingTemplateRead],
)
async def upload_template(
    db: DbSession,
    current_user: CurrentUser,
    file: Annotated[UploadFile, File()],
    name: Annotated[str | None, Form()] = None,
    description: Annotated[str | None, Form()] = None,
    category: Annotated[str | None, Form()] = None,
) -> Envelope[MeetingTemplateRead]:
    content = await file.read()
    template = meeting_template_service.upload_template(
        db,
        user_id=current_user.user_id,
        file_name=file.filename or "template",
        content=content,
        name=name,
        description=description,
        category=category,
    )
    return Envelope(data=_custom_read(template))


@router.post(
    "/meeting-templates/text",
    status_code=status.HTTP_201_CREATED,
    response_model=Envelope[MeetingTemplateRead],
)
def create_template_text(
    payload: TemplateTextCreate, db: DbSession, current_user: CurrentUser
) -> Envelope[MeetingTemplateRead]:
    template = meeting_template_service.create_template_text(
        db,
        user_id=current_user.user_id,
        name=payload.name,
        description=payload.description,
        category=payload.category,
        content_text=payload.content_text,
    )
    return Envelope(data=_custom_read(template))


@router.post(
    "/meeting-templates/generate",
    response_model=Envelope[TemplateGenerateDraft],
)
def generate_template(
    payload: TemplateGenerateRequest, db: DbSession, current_user: CurrentUser
) -> Envelope[TemplateGenerateDraft]:
    """按需求描述用 AI 生成模板草稿（候选结果，不入库；确认后走 text 端点保存）。"""
    draft = meeting_template_service.generate_template_draft(
        db, current_user.user_id, payload.description
    )
    return Envelope(data=TemplateGenerateDraft.model_validate(draft))


@router.get(
    "/meeting-templates/{template_id}",
    response_model=Envelope[MeetingTemplateDetailRead],
)
def get_template(
    template_id: str, db: DbSession, current_user: CurrentUser
) -> Envelope[MeetingTemplateDetailRead]:
    builtin = {
        item["template_id"]: item for item in meeting_template_service.BUILTIN_TEMPLATES
    }.get(template_id)
    if builtin is not None:
        detail = MeetingTemplateDetailRead(
            template_id=builtin["template_id"],
            name=builtin["name"],
            description=builtin["description"],
            category=builtin["category"],
            source="builtin",
            file_name=None,
            created_at=None,
            content_text=builtin["content_text"],
            content_preview=meeting_template_service.preview_text(builtin["content_text"]),
        )
        return Envelope(data=detail)
    template = meeting_template_service.get_owned_template(
        db, template_id, current_user.user_id
    )
    detail = MeetingTemplateDetailRead(
        **_custom_read(template).model_dump(), content_text=template.content_text
    )
    return Envelope(data=detail)


@router.delete(
    "/meeting-templates/{template_id}",
    response_model=Envelope[MeetingTemplateDeleteResult],
)
def delete_template(
    template_id: str, db: DbSession, current_user: CurrentUser
) -> Envelope[MeetingTemplateDeleteResult]:
    meeting_template_service.delete_template(db, template_id, current_user.user_id)
    return Envelope(data=MeetingTemplateDeleteResult(deleted=True))
