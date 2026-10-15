from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.user import utc_now


class UserModelConfig(Base):
    __tablename__ = "user_model_configs"

    user_id: Mapped[str] = mapped_column(
        String(40), ForeignKey("users.user_id"), primary_key=True
    )
    llm_api_base: Mapped[str | None] = mapped_column(String(255), nullable=True)
    llm_api_key_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    llm_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    embedding_api_base: Mapped[str | None] = mapped_column(String(255), nullable=True)
    embedding_api_key_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    embedding_dim: Mapped[int | None] = mapped_column(Integer, nullable=True)
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
