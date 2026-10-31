from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class PreparationStatus(StrEnum):
    generating = "generating"
    draft = "draft"
    confirmed = "confirmed"
    failed = "failed"


class PreparationGenerateRequest(BaseModel):
    include_history: bool = True
    user_goal: str | None = None
    # 可选：覆盖本次生成使用的模型名，必须已在模型配置中登记
    model: str | None = Field(default=None, max_length=100)
    # 可选：套用输出模板（内置或本人自定义）
    template_id: str | None = Field(default=None, max_length=40)


class PreparationUpdate(BaseModel):
    summary: str | None = None
    checklist: list[str] | None = None


class PreparationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    preparation_id: str
    meeting_id: str
    summary: str
    checklist: list[str]
    status: PreparationStatus
    version: int
    created_at: datetime
    updated_at: datetime
