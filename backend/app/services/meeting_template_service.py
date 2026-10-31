from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from app.ai.parsers import parse_bytes
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.models.meeting_template import MeetingTemplate
from app.repositories import meeting_template_repository
from app.utils import storage
from app.utils.ids import new_id

_ALLOWED_EXTENSIONS = ("docx", "txt", "md")
_MAX_CONTENT_CHARS = 20000
_MAX_NAME_CHARS = 100
_MAX_DESCRIPTION_CHARS = 255

# 内置常见模板：不入库，仅代码常量；template_id 使用稳定前缀便于前端引用。
BUILTIN_TEMPLATES: list[dict[str, str]] = [
    {
        "template_id": "tpl-builtin-standard-minutes",
        "name": "标准会议纪要",
        "description": "按议题组织，包含讨论要点、结论与待办事项。",
        "file_name": "",
        "content_text": (
            "1. 会议信息：会议主题、时间、参会人；"
            "2. 议题与讨论：每个议题列出讨论要点与不同意见；"
            "3. 结论与决议：明确达成的决定；"
            "4. 待办事项：任务、负责人、截止时间；"
            "5. 遗留问题：未达成一致、需要下次讨论的内容。"
        ),
    },
    {
        "template_id": "tpl-builtin-concise-minutes",
        "name": "简洁会议纪要",
        "description": "只保留关键结论、决议和待办，优先短段落与要点。",
        "file_name": "",
        "content_text": (
            "1. 核心结论（不超过 5 条）；"
            "2. 决议清单：每条注明决策内容与影响范围；"
            "3. 待办清单：任务、负责人、截止时间。"
        ),
    },
    {
        "template_id": "tpl-builtin-task-list",
        "name": "任务清单纪要",
        "description": "按任务组织，突出负责人与截止时间，未提及写“未指定”。",
        "file_name": "",
        "content_text": (
            "按任务逐条输出：任务名称、负责人、截止时间、验收标准、依赖与风险；"
            "未提及负责人或截止时间时写“未指定”，不得编造。"
        ),
    },
    {
        "template_id": "tpl-builtin-brainstorm",
        "name": "头脑风暴纪要",
        "description": "发散点子分组归类，标注优先级与下一步探索项。",
        "file_name": "",
        "content_text": (
            "1. 本轮目标与约束；"
            "2. 点子清单：按主题分组归类，保留原始表述；"
            "3. 优先级评估：高 / 中 / 低，并说明理由；"
            "4. 下一步：值得深入探索的点子与负责人。"
        ),
    },
    {
        "template_id": "tpl-builtin-retrospective",
        "name": "复盘总结纪要",
        "description": "面向项目复盘：背景、结果、原因分析与改进项。",
        "file_name": "",
        "content_text": (
            "1. 背景与目标：当初的预期；"
            "2. 实际结果：数据与事实；"
            "3. 原因分析：做得好的、不足的；"
            "4. 改进项：可执行的行动、负责人、时间点；"
            "5. 经验沉淀：可复用到其他项目的做法。"
        ),
    },
]

_BUILTIN_INDEX = {item["template_id"]: item for item in BUILTIN_TEMPLATES}


def _builtin_read(item: dict[str, str]) -> dict[str, object]:
    return {
        "template_id": item["template_id"],
        "name": item["name"],
        "description": item["description"],
        "source": "builtin",
        "file_name": None,
        "created_at": None,
    }


def _not_found() -> AppError:
    return AppError("RESOURCE_NOT_FOUND", "模板不存在或不可访问", http_status=404)


def list_templates(db: Session, user_id: str) -> list[dict[str, object]]:
    items: list[dict[str, object]] = [_builtin_read(item) for item in BUILTIN_TEMPLATES]
    for row in meeting_template_repository.list_by_user(db, user_id):
        items.append(
            {
                "template_id": row.template_id,
                "name": row.name,
                "description": row.description,
                "source": "custom",
                "file_name": row.file_name,
                "created_at": row.created_at,
            }
        )
    return items


def resolve_template_content(db: Session, user_id: str, template_id: str) -> str:
    """按 template_id 取模板结构文本：内置优先，其次本人自定义，用于注入生成 prompt。"""
    builtin = _BUILTIN_INDEX.get(template_id)
    if builtin is not None:
        return builtin["content_text"]
    row = meeting_template_repository.get_owned(db, template_id, user_id)
    if row is None:
        raise _not_found()
    return row.content_text


def upload_template(
    db: Session,
    *,
    user_id: str,
    file_name: str,
    content: bytes,
    name: str | None,
    description: str | None,
) -> MeetingTemplate:
    extension = Path(file_name).suffix.lower().lstrip(".")
    if extension not in _ALLOWED_EXTENSIONS:
        raise AppError(
            "FILE_TYPE_NOT_SUPPORTED",
            "不支持的模板类型，仅支持 DOCX、TXT、MD",
            http_status=415,
        )

    settings = get_settings()
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise AppError(
            "FILE_TOO_LARGE",
            f"文件超过大小限制（{settings.max_upload_mb}MB）",
            http_status=413,
        )

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
    storage.save_bytes(settings.storage_dir, relative_key=storage_key, data=content)
    try:
        return meeting_template_repository.create(
            db,
            template_id=template_id,
            user_id=user_id,
            name=cleaned_name,
            description=cleaned_description,
            file_name=file_name,
            storage_key=storage_key,
            content_text=content_text,
        )
    except Exception:
        storage.delete_object(settings.storage_dir, storage_key)
        raise


def get_owned_template(db: Session, template_id: str, user_id: str) -> MeetingTemplate:
    template = meeting_template_repository.get_owned(db, template_id, user_id)
    if template is None:
        raise _not_found()
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
