from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.ai.embeddings import EmbeddingClient
from app.ai.indexing import split_text
from app.models.chunk import DocumentChunk
from app.models.material import MeetingMaterial
from app.repositories import chunk_repository
from app.services.model_config_service import build_embedding_client, resolve_model_config
from app.utils.ids import new_id

logger = logging.getLogger(__name__)

CHUNK_SIZE = 800
CHUNK_OVERLAP = 120


def embed_texts(texts: list[str], client: EmbeddingClient) -> list[list[float]]:
    return client.embed(texts)


def index_material(db: Session, material: MeetingMaterial) -> list[DocumentChunk]:
    config = resolve_model_config(db, material.user_id)
    client = build_embedding_client(config)
    chunk_repository.delete_by_material(db, material.material_id)
    texts = split_text(
        material.content or "", chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP
    )
    if not texts:
        db.commit()
        return []
    vectors = embed_texts(texts, client)
    rows: list[DocumentChunk] = []
    for index, (text, vector) in enumerate(zip(texts, vectors, strict=True)):
        chunk = DocumentChunk(
            chunk_id=new_id("chk"),
            material_id=material.material_id,
            content=text,
            chunk_index=index,
            embedding=vector,
        )
        db.add(chunk)
        rows.append(chunk)
    db.commit()
    for chunk in rows:
        db.refresh(chunk)
    logger.info("材料索引完成 material_id=%s chunks=%d", material.material_id, len(rows))
    return rows
