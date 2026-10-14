from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.user import utc_now


class PersonalTask(Base):
    __tablename__ = "personal_tasks"

    task_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(40), ForeignKey("users.user_id"), nullable=False, index=True
    )
    meeting_id: Mapped[str | None] = mapped_column(
        String(40), ForeignKey("meetings.meeting_id"), nullable=True, index=True
    )
    action_id: Mapped[str | None] = mapped_column(
        String(40), ForeignKey("action_items.action_id"), nullable=True, unique=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="todo", server_default="todo"
    )
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
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
