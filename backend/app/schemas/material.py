from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class ProcessingStatus(StrEnum):
    uploaded = "uploaded"
    processing = "processing"
    processed = "processed"
    failed = "failed"


class MaterialRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    material_id: str
    meeting_id: str
    file_name: str
    type: str
    source: str | None
    processing_status: ProcessingStatus
    parse_error: str | None
    created_at: datetime
