from __future__ import annotations

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.user import utc_now

EMBEDDING_DIM = 1024
_embedding_type = Vector(EMBEDDING_DIM).with_variant(JSON(), "sqlite")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint("material_id", "chunk_index", name="uq_document_chunks_material_index"),
    )

    chunk_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    material_id: Mapped[str] = mapped_column(
        String(40), ForeignKey("meeting_materials.material_id"), nullable=False, index=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(_embedding_type, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, server_default=func.now()
    )
