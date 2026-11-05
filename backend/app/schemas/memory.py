from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.minutes import MinutesTemplate

# 默认纪要模板可选值：内置枚举值（standard/concise/task_list）或模板清单中的模板 id
_VALID_ENUM_VALUES = {
    member.value for member in MinutesTemplate if member is not MinutesTemplate.custom
}


class MemoryWrite(BaseModel):
    role: str | None = Field(default=None, max_length=100)
    work_scenarios: str | None = Field(default=None, max_length=2000)
    communication_style: str | None = Field(default=None, max_length=2000)
    preferred_minutes_template: str | None = Field(default=None, max_length=64)


class MemoryRead(BaseModel):
    role: str
    work_scenarios: str
    communication_style: str
    preferred_minutes_template: str | None
    updated_at: datetime | None


class MemoryDeleteResult(BaseModel):
    deleted: bool = True


def is_builtin_template_value(value: str) -> bool:
    """判断默认模板值是否为内置枚举（否则视为模板清单中的模板 id）。"""
    return value in _VALID_ENUM_VALUES
