from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.user import utc_now


class ActionItem(Base):
    __tablename__ = "action_items"

    action_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    meeting_id: Mapped[str] = mapped_column(
        String(40), ForeignKey("meetings.meeting_id"), nullable=False, index=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    assignee: Mapped[str | None] = mapped_column(String(100), nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="pending_confirmation",
        server_default="pending_confirmation",
    )
    source_record_id: Mapped[str | None] = mapped_column(
        String(40), ForeignKey("meeting_records.record_id"), nullable=True
    )
    source_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
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
