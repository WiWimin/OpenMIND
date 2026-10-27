from __future__ import annotations

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.embeddings import EmbeddingClient
from app.ai.indexing import split_text
from app.ai.parsers import SUPPORTED_EXTENSIONS, parse_bytes
from app.ai.rag.similarity import cosine
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.models.knowledge_chunk import KnowledgeChunk
from app.models.knowledge_document import KnowledgeDocument
from app.repositories import knowledge_chunk_repository, knowledge_repository
from app.services.model_config_service import (
    ModelConfig,
    build_embedding_client,
    resolve_model_config,
)
from app.utils import storage
from app.utils.ids import new_id

CHUNK_SIZE = 800
CHUNK_OVERLAP = 120

_ALLOWED_TYPES = {extension.lstrip(".") for extension in SUPPORTED_EXTENSIONS}


def embed_texts(texts: list[str], client: EmbeddingClient) -> list[list[float]]:
    return client.embed(texts)


def embed_query(text: str, config: ModelConfig) -> list[float]:
    vectors = build_embedding_client(config).embed([text])
    return [float(value) for value in vectors[0]] if vectors else []


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
    vectors = embed_texts(texts, client)
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
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise AppError(
            "FILE_TOO_LARGE",
            f"文件超过大小限制（{settings.max_upload_mb}MB）",
            http_status=413,
        )

    document_id = new_id("kdoc")
    storage_key = f"knowledge/{document_id}.{document_type}"
    storage.save_bytes(settings.storage_dir, relative_key=storage_key, data=content)
    try:
        document = knowledge_repository.create(
            db,
            document_id=document_id,
            user_id=user_id,
            file_name=file_name,
            document_type=document_type,
            storage_key=storage_key,
        )
    except Exception:
        storage.delete_object(settings.storage_dir, storage_key)
        raise
    _process_document(db, document, content, file_name)
    return document


def list_documents(
    db: Session, *, user_id: str, page: int, page_size: int
) -> tuple[list[KnowledgeDocument], int]:
    offset = (page - 1) * page_size
    items = knowledge_repository.list_by_user(
        db, user_id, limit=page_size, offset=offset
    )
    total = knowledge_repository.count_by_user(db, user_id)
    return items, total


def get_owned_document(
    db: Session, document_id: str, user_id: str
) -> KnowledgeDocument:
    document = knowledge_repository.get_owned(db, document_id, user_id)
    if document is None:
        raise AppError(
            "RESOURCE_NOT_FOUND", "知识库文档不存在或不可访问", http_status=404
        )
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
) -> list[tuple[KnowledgeChunk, str, float]]:
    config = resolve_model_config(db, user_id)
    query_vector = embed_query(query, config)
    if not query_vector:
        return []

    statement = (
        select(KnowledgeChunk, KnowledgeDocument.file_name)
        .join(
            KnowledgeDocument,
            KnowledgeChunk.document_id == KnowledgeDocument.document_id,
        )
        .where(
            KnowledgeDocument.user_id == user_id,
            KnowledgeChunk.embedding.is_not(None),
        )
    )
    rows = db.execute(statement).all()
    scored: list[tuple[KnowledgeChunk, str, float]] = []
    for chunk, file_name in rows:
        score = cosine(query_vector, [float(value) for value in chunk.embedding])
        if score >= min_score:
            scored.append((chunk, file_name, score))
    scored.sort(key=lambda item: item[2], reverse=True)
    return scored[:top_k]
