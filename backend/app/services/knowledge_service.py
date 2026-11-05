from __future__ import annotations

import logging
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


def _process_document(
    db: Session, document: KnowledgeDocument, content: bytes, file_name: str
) -> None:
    document.processing_status = "processing"
    try:
        parsed = parse_bytes(content, file_name)
        document.content = parsed.content
        _index_document(db, document)
        document.processing_status = "processed"
        document.parse_error = None
    except AppError as exc:
        document.processing_status = "failed"
        document.parse_error = exc.message
    except Exception:
        logger.exception("知识库索引失败 document_id=%s", document.document_id)
        document.processing_status = "failed"
        document.parse_error = "知识库索引失败"
    finally:
        db.commit()
        db.refresh(document)


def upload_document(
    db: Session, *, user_id: str, file_name: str, content: bytes
) -> KnowledgeDocument:
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
