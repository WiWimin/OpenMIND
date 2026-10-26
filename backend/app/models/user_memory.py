from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.user import utc_now


class UserMemory(Base):
    __tablename__ = "user_memories"

    user_id: Mapped[str] = mapped_column(
        String(40), ForeignKey("users.user_id"), primary_key=True
    )
    role: Mapped[str | None] = mapped_column(String(100), nullable=True)
    work_scenarios: Mapped[str | None] = mapped_column(Text, nullable=True)
    communication_style: Mapped[str | None] = mapped_column(Text, nullable=True)
    preferred_minutes_template: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )
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
