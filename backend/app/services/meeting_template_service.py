from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.ai.parsers import parse_bytes
from app.ai.prompts import build_template_draft
from app.core.config import get_settings
from app.core.exceptions import AppError, resource_not_found
from app.models.meeting_template import MeetingTemplate
from app.repositories import meeting_template_repository
from app.services.model_config_service import (
    ModelPurpose,
    build_llm_client,
    resolve_model_config,
)
from app.utils import storage
from app.utils.ids import new_id
from app.utils.storage import ensure_upload_size

_ALLOWED_EXTENSIONS = ("docx", "txt", "md")
_MAX_CONTENT_CHARS = 20000
_MAX_NAME_CHARS = 100
_MAX_DESCRIPTION_CHARS = 255
_CATEGORIES = ("会前", "会后", "通用")
_PREVIEW_CHARS = 60

# 内置常见模板：不入库，仅代码常量；template_id 使用稳定前缀便于前端引用。
BUILTIN_TEMPLATES: list[dict[str, str]] = [
    {
        "template_id": "tpl-builtin-pre-summary",
        "name": "会前摘要",
        "category": "会前",
        "description": "会前速览材料：核心要点、关键数据与需要提前思考的问题。",
        "content_text": (
            "1. 会议目标：本次会议要解决或决策什么；"
            "2. 材料要点：每份材料的核心结论与关键数据；"
            "3. 需要提前思考的问题：会上可能被问到的内容；"
            "4. 建议关注：与自己职责相关的风险与机会。"
        ),
    },
    {
        "template_id": "tpl-builtin-agenda",
        "name": "会议议程",
        "category": "会前",
        "description": "结构化议程：议题、时长、主持人与预期产出。",
        "content_text": (
            "1. 会议信息：主题、时间、地点、参会人；"
            "2. 议程逐项列出：议题、主持人、时长、讨论方式；"
            "3. 每个议题的预期产出：决策、信息同步或方案确认；"
            "4. 会前准备要求：需要提前阅读或准备的材料。"
        ),
    },
    {
        "template_id": "tpl-builtin-speech",
        "name": "发言稿",
        "category": "会前",
        "description": "结构化发言稿：开场、核心要点、数据支撑与结束语。",
        "content_text": (
            "1. 开场：说明发言目的，结论先行；"
            "2. 核心要点：分点陈述，每点配事实或数据支撑；"
            "3. 风险与请求：需要会议决策或协调的事项；"
            "4. 结束语：总结要点并明确下一步。"
        ),
    },
    {
        "template_id": "tpl-builtin-minutes",
        "name": "会议纪要",
        "category": "会后",
        "description": "标准纪要：议题讨论、结论决议、待办与遗留问题。",
        "content_text": (
            "1. 会议信息：会议主题、时间、参会人；"
            "2. 议题与讨论：每个议题列出讨论要点与不同意见；"
            "3. 结论与决议：明确达成的决定；"
            "4. 待办事项：任务、负责人、截止时间；"
            "5. 遗留问题：未达成一致、需要下次讨论的内容。"
        ),
    },
    {
        "template_id": "tpl-builtin-record",
        "name": "会议记录",
        "category": "会后",
        "description": "完整过程记录：按时间线保留发言要点与原始表述。",
        "content_text": (
            "1. 会议基本信息与参会人；"
            "2. 按时间线逐项记录：每个环节的发言要点，保留关键原始表述；"
            "3. 会上引用的补充材料或数据；"
            "4. 现场争议与不同意见，不做倾向性归纳；"
            "5. 附：被提及但未展开的事项。"
        ),
    },
    {
        "template_id": "tpl-builtin-briefing",
        "name": "会议简报",
        "category": "通用",
        "description": "一页速览：核心结论、关键数字、风险与所需支持。",
        "content_text": (
            "1. 一句话结论：会议最重要的结果；"
            "2. 核心结论（不超过 5 条）；"
            "3. 关键数字：预算、进度、指标变化；"
            "4. 风险与求助：需要上级决策或资源支持的事项；"
            "5. 下一步安排：时间点与负责人。"
        ),
    },
]

_BUILTIN_INDEX = {item["template_id"]: item for item in BUILTIN_TEMPLATES}


def _preview(text: str) -> str:
    cleaned = " ".join(text.split())
    return cleaned[:_PREVIEW_CHARS]


def _builtin_read(item: dict[str, str]) -> dict[str, object]:
    return {
        "template_id": item["template_id"],
        "name": item["name"],
        "description": item["description"],
        "category": item["category"],
        "source": "builtin",
        "file_name": None,
        "created_at": None,
        "content_preview": _preview(item["content_text"]),
    }


def custom_read(row: MeetingTemplate) -> dict[str, object]:
    return {
        "template_id": row.template_id,
        "name": row.name,
        "description": row.description,
        "category": row.category,
        "source": "custom",
        "file_name": row.file_name,
        "created_at": row.created_at,
        "content_preview": _preview(row.content_text),
    }


def preview_text(text: str) -> str:
    """对外暴露的内容预览裁剪（前 60 字符，压平空白）。"""
    return _preview(text or "")


def list_templates(db: Session, user_id: str) -> list[dict[str, object]]:
    items: list[dict[str, object]] = [_builtin_read(item) for item in BUILTIN_TEMPLATES]
    for row in meeting_template_repository.list_by_user(db, user_id):
        items.append(custom_read(row))
    return items


def resolve_template_content(db: Session, user_id: str, template_id: str) -> str:
    """按 template_id 取模板结构文本：内置优先，其次本人自定义，用于注入生成 prompt。"""
    builtin = _BUILTIN_INDEX.get(template_id)
    if builtin is not None:
        return builtin["content_text"]
    row = meeting_template_repository.get_owned(db, template_id, user_id)
    if row is None:
        raise resource_not_found("模板")
    return row.content_text


def upload_template(
    db: Session,
    *,
    user_id: str,
    file_name: str,
    content: bytes,
    name: str | None,
    description: str | None,
    category: str | None = None,
) -> MeetingTemplate:
    cleaned_category = _clean_category(category)
    extension = Path(file_name).suffix.lower().lstrip(".")
    if extension not in _ALLOWED_EXTENSIONS:
        raise AppError(
            "FILE_TYPE_NOT_SUPPORTED",
            "不支持的模板类型，仅支持 DOCX、TXT、MD",
            http_status=415,
        )

    settings = get_settings()
    ensure_upload_size(content, max_mb=settings.max_upload_mb)

    content_text = _extract_text(content, extension)
    cleaned_name = (name or Path(file_name).stem).strip()
    if not cleaned_name:
        raise AppError("VALIDATION_ERROR", "模板名称不能为空", http_status=422)
    if len(cleaned_name) > _MAX_NAME_CHARS:
        raise AppError("VALIDATION_ERROR", "模板名称不能超过 100 个字符", http_status=422)
    cleaned_description = (description or "").strip() or None
    if cleaned_description and len(cleaned_description) > _MAX_DESCRIPTION_CHARS:
        raise AppError(
            "VALIDATION_ERROR", "模板描述不能超过 255 个字符", http_status=422
        )

    template_id = new_id("tpl")
    storage_key = f"templates/{template_id}.{extension}"
    return storage.save_then_create(
        settings.storage_dir,
        storage_key,
        content,
        lambda: meeting_template_repository.create(
            db,
            template_id=template_id,
            user_id=user_id,
            name=cleaned_name,
            description=cleaned_description,
            category=cleaned_category,
            file_name=file_name,
            storage_key=storage_key,
            content_text=content_text,
        ),
    )


def create_template_text(
    db: Session,
    *,
    user_id: str,
    name: str,
    description: str | None = None,
    category: str | None = None,
    content_text: str,
) -> MeetingTemplate:
    """按文本创建自定义模板（用于页面直接粘贴创建、AI 生成确认后的保存与另存为）。"""
    cleaned_name = (name or "").strip()
    if not cleaned_name:
        raise AppError("VALIDATION_ERROR", "模板名称不能为空", http_status=422)
    if len(cleaned_name) > _MAX_NAME_CHARS:
        raise AppError("VALIDATION_ERROR", "模板名称不能超过 100 个字符", http_status=422)
    cleaned_description = (description or "").strip() or None
    if cleaned_description and len(cleaned_description) > _MAX_DESCRIPTION_CHARS:
        raise AppError(
            "VALIDATION_ERROR", "模板描述不能超过 255 个字符", http_status=422
        )
    cleaned_category = _clean_category(category)
    text = (content_text or "").strip()
    if not text:
        raise AppError("VALIDATION_ERROR", "模板内容不能为空", http_status=422)
    if len(text) > _MAX_CONTENT_CHARS:
        raise AppError(
            "VALIDATION_ERROR",
            f"模板内容不能超过 {_MAX_CONTENT_CHARS} 字符",
            http_status=422,
        )
    return meeting_template_repository.create(
        db,
        template_id=new_id("tpl"),
        user_id=user_id,
        name=cleaned_name,
        description=cleaned_description,
        category=cleaned_category,
        content_text=text,
    )


class _GeneratedTemplate(BaseModel):
    """LLM 生成模板草稿的输出契约（chat_json 校验）。"""

    name: str
    description: str = ""
    category: str = "通用"
    content_text: str


def generate_template_draft(db: Session, user_id: str, description: str) -> dict[str, str]:
    """按需求描述让 LLM 生成模板草稿，返回候选结果，不入库（用户确认后另行保存）。"""
    text = (description or "").strip()
    if not text:
        raise AppError("VALIDATION_ERROR", "请描述模板需求", http_status=422)
    if len(text) > 500:
        raise AppError("VALIDATION_ERROR", "模板需求描述不能超过 500 字符", http_status=422)

    config = resolve_model_config(db, user_id, purpose=ModelPurpose.minutes)
    client = build_llm_client(config)
    prompt = build_template_draft(text)
    try:
        draft = client.chat_json(
            [{"role": "user", "content": prompt}],
            schema=_GeneratedTemplate,
            temperature=0.4,
        )
    except AppError as exc:
        raise AppError(
            exc.error_code,
            f"AI 生成模板失败：{exc.message}",
            http_status=exc.http_status,
            retryable=exc.retryable,
        ) from None

    name = draft.name.strip()[:_MAX_NAME_CHARS] or "未命名模板"
    cleaned_description = draft.description.strip()[:_MAX_DESCRIPTION_CHARS] or None
    content = draft.content_text.strip()[:_MAX_CONTENT_CHARS]
    if not content:
        raise AppError("MODEL_OUTPUT_INVALID", "AI 生成的模板内容为空", http_status=502)
    return {
        "name": name,
        "description": cleaned_description or "",
        "category": _clean_category(draft.category) or "通用",
        "content_text": content,
    }


def _clean_category(category: str | None) -> str | None:
    cleaned = (category or "").strip()
    if not cleaned:
        return None
    if cleaned not in _CATEGORIES:
        raise AppError("VALIDATION_ERROR", "分类仅支持：会前、会后、通用", http_status=422)
    return cleaned


def get_owned_template(db: Session, template_id: str, user_id: str) -> MeetingTemplate:
    template = meeting_template_repository.get_owned(db, template_id, user_id)
    if template is None:
        raise resource_not_found("模板")
    return template


def delete_template(db: Session, template_id: str, user_id: str) -> None:
    template = get_owned_template(db, template_id, user_id)
    storage.delete_object(get_settings().storage_dir, template.storage_key)
    meeting_template_repository.delete(db, template)


def _extract_text(content: bytes, extension: str) -> str:
    if extension == "docx":
        try:
            parsed = parse_bytes(content, f"template.{extension}")
        except AppError as exc:
            raise AppError(
                "FILE_PARSE_FAILED", f"模板解析失败：{exc.message}", http_status=422
            ) from None
        text = parsed.content
    else:
        text = _decode_text(content)
    text = text.strip()
    if not text:
        raise AppError("FILE_PARSE_FAILED", "模板内容为空，无法使用", http_status=422)
    if len(text) > _MAX_CONTENT_CHARS:
        text = text[:_MAX_CONTENT_CHARS]
    return text


def _decode_text(content: bytes) -> str:
    for encoding in ("utf-8", "gbk"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise AppError(
        "FILE_PARSE_FAILED", "模板文件编码无法识别，请使用 UTF-8 编码", http_status=422
    )
