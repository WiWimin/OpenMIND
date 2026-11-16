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
    parse_error_code: str | None = None
    created_at: datetime
    # 原始文件大小（由存储层 stat 计算，非数据库列），供本地同步估算下载量
    file_size: int | None = None
