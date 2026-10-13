from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from app.ai.parsers import SUPPORTED_EXTENSIONS
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.models.material import MeetingMaterial
from app.repositories import material_repository
from app.services import meeting_service
from app.utils import storage
from app.utils.ids import new_id

_ALLOWED_TYPES = {extension.lstrip(".") for extension in SUPPORTED_EXTENSIONS}


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
    meeting_service.get_owned_meeting(db, meeting_id, user_id)
    normalized_type = _infer_material_type(file_name, material_type)

    settings = get_settings()
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise AppError(
            "FILE_TOO_LARGE",
            f"文件超过大小限制（{settings.max_upload_mb}MB）",
            http_status=413,
        )

    material_id = new_id("mat")
    storage_key = f"materials/{material_id}.{normalized_type}"
    storage.save_bytes(settings.storage_dir, relative_key=storage_key, data=content)
    try:
        return material_repository.create(
            db,
            material_id=material_id,
            meeting_id=meeting_id,
            user_id=user_id,
            file_name=file_name,
            material_type=normalized_type,
            source=source,
            storage_key=storage_key,
        )
    except Exception:
        storage.delete_object(settings.storage_dir, storage_key)
        raise


def list_materials(
    db: Session,
    *,
    meeting_id: str,
    user_id: str,
    page: int,
    page_size: int,
) -> tuple[list[MeetingMaterial], int]:
    meeting_service.get_owned_meeting(db, meeting_id, user_id)
    offset = (page - 1) * page_size
    items = material_repository.list_by_meeting(
        db, meeting_id, limit=page_size, offset=offset
    )
    total = material_repository.count_by_meeting(db, meeting_id)
    return items, total


def get_owned_material(db: Session, material_id: str, user_id: str) -> MeetingMaterial:
    material = material_repository.get_owned(db, material_id, user_id)
    if material is None:
        raise AppError("RESOURCE_NOT_FOUND", "材料不存在或不可访问", http_status=404)
    return material


def delete_material(db: Session, material_id: str, user_id: str) -> None:
    material = get_owned_material(db, material_id, user_id)
    storage.delete_object(get_settings().storage_dir, material.storage_key)
    material_repository.delete(db, material)
