from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class JobStatus(StrEnum):
    pending = "pending"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"


class JobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    job_id: str
    job_type: str
    status: JobStatus
    resource_type: str
    resource_id: str | None = None
    progress: int
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class JobAccepted(BaseModel):
    """202 受理响应载荷：`data.job` 为任务快照（`api.md 1.9`）。"""

    job: JobRead
