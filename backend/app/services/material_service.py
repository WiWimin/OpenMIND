from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy.orm import Session

from app.ai.parsers import SUPPORTED_EXTENSIONS, parse_bytes
from app.core.config import get_settings
from app.core.exceptions import AppError, resource_not_found
from app.models.material import MeetingMaterial
from app.repositories import chunk_repository, material_repository, record_repository
from app.services import indexing_service, meeting_service
from app.utils import storage
from app.utils.ids import new_id
from app.utils.pagination import paginate_by
from app.utils.storage import ensure_upload_size

_ALLOWED_TYPES = {extension.lstrip(".") for extension in SUPPORTED_EXTENSIONS}

logger = logging.getLogger(__name__)


def _infer_material_type(file_name: str, material_type: str | None) -> str:
    suffix = Path(file_name).suffix.lower().lstrip(".")
    candidate = (material_type or suffix).lower()
    if candidate not in _ALLOWED_TYPES:
        raise AppError(
            "FILE_TYPE_NOT_SUPPORTED",
            "不支持的文件类型，仅支持 PDF、DOCX、TXT",
            http_status=415,
        )
    return candidate


def _mark_failed(
    db: Session, material: MeetingMaterial, *, message: str, code: str
) -> None:
    """统一失败策略：落库 `failed`，保留数据库记录、原始文件与分块清理，供重试使用。"""
    db.rollback()
    # 失败时清掉可能残留的半成品分块，避免 failed 记录带脏索引
    chunk_repository.delete_by_material(db, material.material_id)
    material.processing_status = "failed"
    material.parse_error = message
    material.parse_error_code = code
    db.commit()
    db.refresh(material)


def _process_material(
    db: Session, material: MeetingMaterial, content: bytes, file_name: str
) -> None:
    """解析 + 索引：成功转 `processed`，失败转 `failed` 并保留记录与文件（可重试）。"""
    material.processing_status = "processing"
    db.commit()
    try:
        parsed = parse_bytes(content, file_name)
        material.content = parsed.content
        indexing_service.index_material(db, material)
        material.processing_status = "processed"
        material.parse_error = None
        material.parse_error_code = None
        db.commit()
        db.refresh(material)
    except AppError as exc:
        _mark_failed(db, material, message=exc.message, code=exc.error_code)
    except Exception:
        logger.exception("材料处理出现未预期异常 material_id=%s", material.material_id)
        _mark_failed(db, material, message="材料处理失败，请重试", code="INTERNAL_ERROR")


def upload_material(
    db: Session,
    *,
    meeting_id: str,
    user_id: str,
    file_name: str,
    content: bytes,
    source: str | None,
    material_type: str | None,
) -> MeetingMaterial:
    meeting_service.get_mutable_meeting(db, meeting_id, user_id)
    normalized_type = _infer_material_type(file_name, material_type)

    settings = get_settings()
    ensure_upload_size(content, max_mb=settings.max_upload_mb)

    material_id = new_id("mat")
    storage_key = f"materials/{material_id}.{normalized_type}"
    material = storage.save_then_create(
        settings.storage_dir,
        storage_key,
        content,
        lambda: material_repository.create(
            db,
            material_id=material_id,
            meeting_id=meeting_id,
            user_id=user_id,
            file_name=file_name,
            material_type=normalized_type,
            source=source,
            storage_key=storage_key,
        ),
    )
    # 失败不再回滚清理：记录与文件保留为 failed，由重试接口处理（docs/database.md 统一策略）
    _process_material(db, material, content, file_name)
    return material


def retry_material(db: Session, material_id: str, user_id: str) -> MeetingMaterial:
    """重新解析/索引处理失败的材料（仅 `failed` 可重试，读取磁盘原文件）。"""
    material = get_owned_material(db, material_id, user_id)
    meeting_service.get_mutable_meeting(db, material.meeting_id, user_id)
    if material.processing_status == "processing":
        raise AppError(
            "BUSINESS_RULE_VIOLATION",
            "材料正在处理中，请稍候再试",
            http_status=409,
            details={"reason": "material_processing"},
        )
    if material.processing_status != "failed":
        raise AppError(
            "BUSINESS_RULE_VIOLATION",
            "仅处理失败的材料可重试",
            http_status=409,
            details={"reason": "material_not_failed"},
        )
    settings = get_settings()
    try:
        content = storage.read_bytes(settings.storage_dir, material.storage_key)
    except FileNotFoundError:
        raise AppError(
            "RESOURCE_NOT_FOUND",
            "原始文件已丢失，请重新上传",
            http_status=404,
        ) from None
    _process_material(db, material, content, material.file_name)
    return material


def list_materials(
    db: Session,
    *,
    meeting_id: str,
    user_id: str,
    page: int,
    page_size: int,
) -> tuple[list[MeetingMaterial], int]:
    meeting_service.get_owned_meeting(db, meeting_id, user_id)
    return paginate_by(
        material_repository.list_by_meeting,
        material_repository.count_by_meeting,
        db,
        meeting_id,
        page=page,
        page_size=page_size,
    )


def get_owned_material(db: Session, material_id: str, user_id: str) -> MeetingMaterial:
    material = material_repository.get_owned(db, material_id, user_id)
    if material is None:
        raise resource_not_found("材料")
    return material


def delete_material(db: Session, material_id: str, user_id: str) -> None:
    material = get_owned_material(db, material_id, user_id)
    meeting_service.get_mutable_meeting(db, material.meeting_id, user_id)
    record_repository.clear_source_material(db, material_id)
    storage.delete_object(get_settings().storage_dir, material.storage_key)
    chunk_repository.delete_by_material(db, material_id)
    material_repository.delete(db, material)
