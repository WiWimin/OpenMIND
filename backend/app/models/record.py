from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.user import utc_now


class MeetingRecord(Base):
    __tablename__ = "meeting_records"
    __table_args__ = (
        # 幂等键：同一 client_op_id 只允许落一条记录（迁移 0027）
        Index("uq_meeting_records_client_op_id", "client_op_id", unique=True),
    )

    record_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    meeting_id: Mapped[str] = mapped_column(
        String(40), ForeignKey("meetings.meeting_id"), nullable=False, index=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    record_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="manual", server_default="manual"
    )
    marker_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    client_op_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_material_id: Mapped[str | None] = mapped_column(
        String(40), ForeignKey("meeting_materials.material_id"), nullable=True
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
