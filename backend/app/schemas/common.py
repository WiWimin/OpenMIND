from __future__ import annotations

from typing import Generic, Literal, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Envelope(BaseModel, Generic[T]):
    """成功响应统一信封（`api.md 一.1`，D-07）。"""

    status: Literal["success"] = "success"
    data: T


class Pagination(BaseModel):
    page: int
    page_size: int
    total: int
    total_pages: int


class ListData(BaseModel, Generic[T]):
    """列表分页载荷（`api.md 一.4`，D-10）。"""

    items: list[T]
    pagination: Pagination


class MeetingDeleteResult(BaseModel):
    deleted: bool = True
    meeting_id: str


class MaterialDeleteResult(BaseModel):
    deleted: bool = True
    material_id: str
