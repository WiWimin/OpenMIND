from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from sqlalchemy.orm import Session

from app.ai.indexing import build_index_fingerprint, file_sha256
from app.ai.parsers import SUPPORTED_EXTENSIONS, parse_bytes
from app.core.config import get_settings
from app.core.exceptions import AppError, resource_not_found
from app.models.material import MeetingMaterial
from app.models.user import utc_now
from app.repositories import chunk_repository, material_repository, record_repository
from app.services import indexing_service, meeting_service, sync_support
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


def _try_reuse_index(
    db: Session,
    material: MeetingMaterial,
    content: bytes,
    *,
    fingerprint: str,
    progress_cb: Callable[[int], None] | None = None,
) -> bool:
    """增量索引：命中同用户、同内容、同指纹的已索引材料则复用其分块。

    复用范围仅限会议材料库内（可跨会议），不跨到知识库；
    命中即跳过解析与向量化（零 Embedding 调用），返回 True。
    """
    settings = get_settings()
    if not settings.rag_incremental_index_enabled:
        return False
    content_hash = material.content_hash or file_sha256(content)
    source = material_repository.find_reusable_index(
        db,
        user_id=material.user_id,
        content_hash=content_hash,
        fingerprint=fingerprint,
        exclude_material_id=material.material_id,
    )
    if source is None or not source.content:
        return False
    copied = chunk_repository.copy_by_material(
        db, source.material_id, material.material_id
    )
    material.content = source.content
    material.processing_status = "processed"
    material.parse_error = None
    material.parse_error_code = None
    material.index_fingerprint = fingerprint
    material.indexed_at = utc_now()
    db.commit()
    db.refresh(material)
    if progress_cb:
        progress_cb(90)
    logger.info(
        "增量索引复用 material_id=%s source_material_id=%s chunks=%d",
        material.material_id,
        source.material_id,
        copied,
    )
    return True


def _process_material(
    db: Session,
    material: MeetingMaterial,
    content: bytes,
    file_name: str,
    *,
    progress_cb: Callable[[int], None] | None = None,
) -> str:
    """解析 + 索引：成功转 `processed`，失败转 `failed` 并保留记录与文件（可重试）。

    增量索引：同用户、同库内命中同内容、同指纹的已索引记录时直接复用分块，
    跳过解析与向量化。返回终态 `processed` / `failed`；异步任务（`job_tasks`）据此判定任务成败。
    """
    fingerprint = build_index_fingerprint(get_settings())
    material.processing_status = "processing"
    material.content_hash = material.content_hash or file_sha256(content)
    db.commit()
    if progress_cb:
        progress_cb(10)
    try:
        if _try_reuse_index(
            db, material, content, fingerprint=fingerprint, progress_cb=progress_cb
        ):
            return "processed"
        parsed = parse_bytes(content, file_name)
        material.content = parsed.content
        if progress_cb:
            progress_cb(60)
        indexing_service.index_material(db, material)
        material.processing_status = "processed"
        material.parse_error = None
        material.parse_error_code = None
        material.index_fingerprint = fingerprint
        material.indexed_at = utc_now()
        db.commit()
        db.refresh(material)
        if progress_cb:
            progress_cb(90)
        return "processed"
    except AppError as exc:
        _mark_failed(db, material, message=exc.message, code=exc.error_code)
        return "failed"
    except Exception:
        logger.exception("材料处理出现未预期异常 material_id=%s", material.material_id)
        _mark_failed(db, material, message="材料处理失败，请重试", code="INTERNAL_ERROR")
        return "failed"


def upload_material(
    db: Session,
    *,
    meeting_id: str,
    user_id: str,
    file_name: str,
    content: bytes,
    source: str | None,
    material_type: str | None,
    defer_processing: bool = False,
    client_op_id: str | None = None,
) -> MeetingMaterial:
    """上传并（同步或交由异步任务）处理材料。

    `defer_processing=True`（异步模式）只落盘建记录（`uploaded`），
    解析/索引由后台任务执行。
    """
    meeting_service.get_mutable_meeting(db, meeting_id, user_id)
    normalized_type = _infer_material_type(file_name, material_type)

    settings = get_settings()
    ensure_upload_size(content, max_mb=settings.max_upload_mb)

    # 幂等键：同一 client_op_id 重复提交只落一条，避免同步重试重复导入
    if client_op_id:
        existing = material_repository.get_by_client_op_id(db, client_op_id)
        if existing is not None:
            if existing.user_id != user_id or existing.meeting_id != meeting_id:
                raise resource_not_found("材料")
            sync_support.ensure_same_payload(
                {"file_name": existing.file_name, "type": existing.type},
                {"file_name": file_name, "type": normalized_type},
            )
            return existing

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
            client_op_id=client_op_id,
        ),
    )
    # 失败不再回滚清理：记录与文件保留为 failed，由重试接口处理（docs/database.md 统一策略）
    if not defer_processing:
        _process_material(db, material, content, file_name)
    return material


def retry_material(
    db: Session, material_id: str, user_id: str, *, defer_processing: bool = False
) -> MeetingMaterial:
    """重新解析/索引处理失败的材料（仅 `failed` 可重试，读取磁盘原文件）。

    `defer_processing=True` 时只做归属/状态/文件存在性校验，
    实际处理交由后台任务。
    """
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
    if not defer_processing:
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


def file_size_of(material: MeetingMaterial) -> int | None:
    """原始文件大小（stat 计算，非数据库列）；文件丢失返回 None。"""
    return storage.stat_size(get_settings().storage_dir, material.storage_key)


def read_material_file(material: MeetingMaterial) -> bytes:
    """读取原始文件内容（下载接口用）；文件已丢失时抛 404。"""
    try:
        return storage.read_bytes(get_settings().storage_dir, material.storage_key)
    except OSError:
        raise AppError(
            "RESOURCE_NOT_FOUND",
            "原始文件已丢失，请重新上传",
            http_status=404,
        ) from None


def delete_material(db: Session, material_id: str, user_id: str) -> None:
    material = get_owned_material(db, material_id, user_id)
    meeting_service.get_mutable_meeting(db, material.meeting_id, user_id)
    record_repository.clear_source_material(db, material_id)
    storage.delete_object(get_settings().storage_dir, material.storage_key)
    chunk_repository.delete_by_material(db, material_id)
    material_repository.delete(db, material)
