from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.sync import OptimisticLockMixin


class RecordType(StrEnum):
    manual = "manual"
    transcript = "transcript"
    imported = "imported"


class RecordMarkerType(StrEnum):
    highlight = "highlight"
    decision = "decision"
    question = "question"


class RecordCreate(BaseModel):
    content: str = Field(min_length=1)
    record_type: RecordType = RecordType.manual
    marker_type: RecordMarkerType | None = None
    # 幂等键：同一 client_op_id 重复提交只创建一条（迁移 0026）
    client_op_id: str | None = Field(default=None, max_length=64)


class RecordUpdate(OptimisticLockMixin):
    content: str | None = Field(default=None, min_length=1)
    marker_type: RecordMarkerType | None = None


class MeetingRecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    record_id: str
    meeting_id: str
    content: str
    record_type: RecordType
    marker_type: RecordMarkerType | None
    source_material_id: str | None
    created_at: datetime
    updated_at: datetime
