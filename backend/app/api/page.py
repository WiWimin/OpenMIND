"""api 层统一的分页查询依赖与列表响应组装（`docs/api.md 一.4`）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Any, TypeVar

from fastapi import Depends, Query

from app.schemas.common import Envelope, ListData
from app.utils.pagination import build_pagination

_S = TypeVar("_S")


@dataclass
class _PageQuery:
    """所有列表接口共享的 `page` / `page_size` 查询参数。"""

    page: Annotated[int, Query(ge=1)] = 1
    page_size: Annotated[int, Query(ge=1, le=100)] = 20


PageParams = Annotated[_PageQuery, Depends()]


def list_envelope(
    items: Any,
    schema: type[_S],
    *,
    page: int,
    page_size: int,
    total: int,
) -> Envelope[ListData[_S]]:
    """把 (items, total) 组装为统一信封 `Envelope[ListData[Schema]]`。"""
    data = ListData[schema](
        items=[schema.model_validate(item) for item in items],
        pagination=build_pagination(page, page_size, total),
    )
    return Envelope(data=data)
