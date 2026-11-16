from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.user import utc_now


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"
    __table_args__ = (
        # 增量索引：同用户同内容文档可复用分块（迁移 0028）
        Index("ix_knowledge_documents_user_content_hash", "user_id", "content_hash"),
    )

    document_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(40), ForeignKey("users.user_id"), nullable=False, index=True
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 内容摘要（sha256 hex）：增量索引的同内容判定依据（迁移 0028）
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # 索引参数指纹：标识存量分块由哪套参数/模型产出，指纹不匹配不得复用
    index_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # 最近一次成功建索引时间（增量索引复用/重建时更新）
    indexed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    processing_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="uploaded", server_default="uploaded"
    )
    parse_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 解析/索引失败的错误码（如 FILE_PARSE_FAILED / MODEL_CONFIG_REQUIRED），供前端映射文案
    parse_error_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
        server_default=func.now(),
    )
