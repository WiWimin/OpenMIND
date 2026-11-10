"""异步任务体工厂（B3）：每个工厂返回可交给 `task_runner.run_job` 的任务函数。

约定：任务体在独立会话中执行；处理类任务返回/抛出 `AppError` 表达失败，
由执行器写入 `async_jobs.error_code` / `error_message`。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.repositories import knowledge_repository, material_repository
from app.schemas.minutes import MinutesGenerateRequest
from app.services import (
    audio_service,
    knowledge_service,
    material_service,
    minutes_service,
    preparation_service,
)
from app.services.task_runner import JobFn
from app.utils import storage

Progress = Any  # Callable[[int], None]（避免与 JobFn 循环导入，签名一致）

_NOT_FOUND = "RESOURCE_NOT_FOUND"


def _read(storage_key: str) -> bytes:
    try:
        return storage.read_bytes(get_settings().storage_dir, storage_key)
    except OSError:
        raise AppError(
            _NOT_FOUND, "原始文件已丢失，请重新上传", http_status=404
        ) from None


def material_parse(material_id: str, user_id: str) -> JobFn:
    def _run(db: Session, progress: Progress) -> None:
        material = material_repository.get_owned(db, material_id, user_id)
        if material is None:
            raise AppError(_NOT_FOUND, "材料不存在或不可访问", http_status=404)
        content = _read(material.storage_key)
        outcome = material_service._process_material(
            db,
            material,
            content,
            material.file_name,
            progress_cb=progress,
        )
        if outcome == "failed":
            raise AppError(
                material.parse_error_code or "INTERNAL_ERROR",
                material.parse_error or "材料处理失败，请重试",
            )

    return _run


def knowledge_parse(document_id: str, user_id: str) -> JobFn:
    def _run(db: Session, progress: Progress) -> None:
        document = knowledge_repository.get_owned(db, document_id, user_id)
        if document is None:
            raise AppError(_NOT_FOUND, "知识库文档不存在或不可访问", http_status=404)
        content = _read(document.storage_key)
        outcome = knowledge_service._process_document(
            db,
            document,
            content,
            document.file_name,
            progress_cb=progress,
        )
        if outcome == "failed":
            raise AppError(
                document.parse_error_code or "INTERNAL_ERROR",
                document.parse_error or "知识库索引失败，请重试",
            )

    return _run


def audio_transcribe(audio_id: str, user_id: str) -> JobFn:
    def _run(db: Session, progress: Progress) -> None:
        audio = audio_service.get_owned_audio(db, audio_id, user_id)
        content = _read(audio.storage_key)
        error_code = audio_service._run_transcription(
            db, audio, content, audio.file_name, progress_cb=progress
        )
        if error_code:
            raise AppError(error_code, audio.error or "音频转写失败，请重试")

    return _run


def minutes_generate(
    meeting_id: str, user_id: str, payload: MinutesGenerateRequest
) -> JobFn:
    def _run(db: Session, progress: Progress) -> None:
        context = minutes_service.prepare_minutes_context(
            db, meeting_id=meeting_id, user_id=user_id, payload=payload
        )
        minutes_service.run_minutes_generation(db, context, progress_cb=progress)

    return _run


def preparation_generate(
    meeting_id: str,
    user_id: str,
    preparation_id: str,
    *,
    user_goal: str | None,
    include_history: bool = True,
    model: str | None = None,
    template_id: str | None = None,
) -> JobFn:
    def _run(db: Session, progress: Progress) -> None:
        try:
            context = preparation_service.prepare_generation_context(
                db,
                meeting_id=meeting_id,
                user_id=user_id,
                user_goal=user_goal,
                include_history=include_history,
                model=model,
                template_id=template_id,
            )
            preparation_service.run_preparation_generation(
                db,
                context,
                preparation_id=preparation_id,
                progress_cb=progress,
            )
        except Exception:
            # 占位行不能停留在 generating：失败标 failed 后原样上抛给执行器
            try:
                db.rollback()
                preparation_service.mark_generation_failed(db, preparation_id)
            except Exception:  # noqa: BLE001 — 失败标记写不进去也不掩盖原错误
                db.rollback()
            raise

    return _run
