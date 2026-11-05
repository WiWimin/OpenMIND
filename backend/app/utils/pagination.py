from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from app.schemas.common import Pagination

_T = TypeVar("_T")


def build_pagination(page: int, page_size: int, total: int) -> Pagination:
    total_pages = (total + page_size - 1) // page_size if total else 0
    return Pagination(page=page, page_size=page_size, total=total, total_pages=total_pages)


def paginate_by(
    list_fn: Callable[..., list[_T]],
    count_fn: Callable[..., int],
    *args: Any,
    page: int,
    page_size: int,
    **filters: Any,
) -> tuple[list[_T], int]:
    """service 层统一分页查询样板：计算 offset 并同时取回 items 与 total。

    约定 repository 遵循 `list_by_*(db, key, *, filters..., limit, offset)`
    与 `count_by_*(db, key, *, filters...)` 签名。
    """
    offset = (page - 1) * page_size
    items = list_fn(*args, **filters, limit=page_size, offset=offset)
    total = count_fn(*args, **filters)
    return items, total
