from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.user import utc_now

_source_ids_type = JSON().with_variant(postgresql.JSONB(), "postgresql")


class MeetingMinutes(Base):
    __tablename__ = "meeting_minutes"

    minutes_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    meeting_id: Mapped[str] = mapped_column(
        String(40), ForeignKey("meetings.meeting_id"), nullable=False, index=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="draft", server_default="draft"
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    source_record_ids: Mapped[list[str]] = mapped_column(
        _source_ids_type, nullable=False, default=list
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
