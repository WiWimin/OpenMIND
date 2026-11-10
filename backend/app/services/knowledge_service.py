from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from sqlalchemy.orm import Session

from app.ai.indexing import CHUNK_OVERLAP, CHUNK_SIZE, split_text
from app.ai.parsers import SUPPORTED_EXTENSIONS, parse_bytes
from app.ai.rag.retriever import RetrievedChunk, VectorRetriever
from app.core.config import get_settings
from app.core.exceptions import AppError, resource_not_found
from app.models.knowledge_chunk import KnowledgeChunk
from app.models.knowledge_document import KnowledgeDocument
from app.repositories import knowledge_chunk_repository, knowledge_repository
from app.services.model_config_service import build_embedding_client, resolve_model_config
from app.utils import storage
from app.utils.ids import new_id
from app.utils.pagination import paginate_by
from app.utils.storage import ensure_upload_size

logger = logging.getLogger(__name__)

_ALLOWED_TYPES = {extension.lstrip(".") for extension in SUPPORTED_EXTENSIONS}


def _infer_document_type(file_name: str) -> str:
    candidate = Path(file_name).suffix.lower().lstrip(".")
    if candidate not in _ALLOWED_TYPES:
        raise AppError(
            "FILE_TYPE_NOT_SUPPORTED",
            "不支持的文件类型，仅支持 PDF、DOCX、TXT",
            http_status=415,
        )
    return candidate


def _index_document(
    db: Session, document: KnowledgeDocument
) -> None:
    config = resolve_model_config(db, document.user_id)
    client = build_embedding_client(config)
    knowledge_chunk_repository.delete_by_document(db, document.document_id)
    texts = split_text(
        document.content or "", chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP
    )
    if not texts:
        return
    vectors = client.embed(texts)
    for index, (text, vector) in enumerate(zip(texts, vectors, strict=True)):
        db.add(
            KnowledgeChunk(
                chunk_id=new_id("kchk"),
                document_id=document.document_id,
                content=text,
                chunk_index=index,
                embedding=vector,
            )
        )


def _mark_failed(
    db: Session, document: KnowledgeDocument, *, message: str, code: str
) -> None:
    """统一失败策略：落库 `failed`，保留记录与已上传文件，供重试使用。"""
    db.rollback()
    knowledge_chunk_repository.delete_by_document(db, document.document_id)
    document.processing_status = "failed"
    document.parse_error = message
    document.parse_error_code = code
    db.commit()
    db.refresh(document)


def _process_document(
    db: Session,
    document: KnowledgeDocument,
    content: bytes,
    file_name: str,
    *,
    progress_cb: Callable[[int], None] | None = None,
) -> str:
    """解析 + 索引：返回终态 `processed` / `failed`（供异步任务判定成败）。"""
    document.processing_status = "processing"
    db.commit()
    if progress_cb:
        progress_cb(10)
    try:
        parsed = parse_bytes(content, file_name)
        document.content = parsed.content
        if progress_cb:
            progress_cb(60)
        _index_document(db, document)
        document.processing_status = "processed"
        document.parse_error = None
        document.parse_error_code = None
        db.commit()
        db.refresh(document)
        if progress_cb:
            progress_cb(90)
        return "processed"
    except AppError as exc:
        _mark_failed(db, document, message=exc.message, code=exc.error_code)
        return "failed"
    except Exception:
        logger.exception("知识库索引失败 document_id=%s", document.document_id)
        _mark_failed(db, document, message="知识库索引失败", code="INTERNAL_ERROR")
        return "failed"


def upload_document(
    db: Session,
    *,
    user_id: str,
    file_name: str,
    content: bytes,
    defer_processing: bool = False,
) -> KnowledgeDocument:
    """上传并（同步或交由异步任务）处理文档；`defer_processing=True` 只落盘建记录。"""
    document_type = _infer_document_type(file_name)
    settings = get_settings()
    ensure_upload_size(content, max_mb=settings.max_upload_mb)

    document_id = new_id("kdoc")
    storage_key = f"knowledge/{document_id}.{document_type}"
    document = storage.save_then_create(
        settings.storage_dir,
        storage_key,
        content,
        lambda: knowledge_repository.create(
            db,
            document_id=document_id,
            user_id=user_id,
            file_name=file_name,
            document_type=document_type,
            storage_key=storage_key,
        ),
    )
    if not defer_processing:
        _process_document(db, document, content, file_name)
    return document


def list_documents(
    db: Session, *, user_id: str, page: int, page_size: int
) -> tuple[list[KnowledgeDocument], int]:
    return paginate_by(
        knowledge_repository.list_by_user,
        knowledge_repository.count_by_user,
        db,
        user_id,
        page=page,
        page_size=page_size,
    )


def get_owned_document(
    db: Session, document_id: str, user_id: str
) -> KnowledgeDocument:
    document = knowledge_repository.get_owned(db, document_id, user_id)
    if document is None:
        raise resource_not_found("知识库文档")
    return document


def delete_document(db: Session, document_id: str, user_id: str) -> None:
    document = get_owned_document(db, document_id, user_id)
    storage.delete_object(get_settings().storage_dir, document.storage_key)
    knowledge_chunk_repository.delete_by_document(db, document_id)
    knowledge_repository.delete(db, document)


def retry_document(
    db: Session, document_id: str, user_id: str, *, defer_processing: bool = False
) -> KnowledgeDocument:
    """重新解析/索引处理失败的知识库文档（仅 `failed` 可重试，读取磁盘原文件）。

    `defer_processing=True` 时只做状态与文件存在性校验，处理交由后台任务。
    """
    document = get_owned_document(db, document_id, user_id)
    if document.processing_status == "processing":
        raise AppError(
            "BUSINESS_RULE_VIOLATION",
            "文档正在处理中，请稍候再试",
            http_status=409,
            details={"reason": "document_processing"},
        )
    if document.processing_status != "failed":
        raise AppError(
            "BUSINESS_RULE_VIOLATION",
            "仅处理失败的文档可重试",
            http_status=409,
            details={"reason": "document_not_failed"},
        )
    settings = get_settings()
    try:
        content = storage.read_bytes(settings.storage_dir, document.storage_key)
    except FileNotFoundError:
        raise AppError(
            "RESOURCE_NOT_FOUND",
            "原始文件已丢失，请重新上传",
            http_status=404,
        ) from None
    if not defer_processing:
        _process_document(db, document, content, document.file_name)
    return document


def search_documents(
    db: Session,
    *,
    user_id: str,
    query: str,
    top_k: int,
    min_score: float,
) -> list[RetrievedChunk]:
    """知识库语义检索：委托 ai 层 VectorRetriever 的统一实现。"""
    return VectorRetriever(db, user_id).retrieve_knowledge(
        query,
        user_id=user_id,
        top_k=top_k,
        min_score=min_score,
    )
