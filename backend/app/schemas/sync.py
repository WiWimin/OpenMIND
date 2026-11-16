"""本地工作区双向同步相关的请求字段（docs/api.md 一.3）。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class OptimisticLockMixin(BaseModel):
    """乐观锁前置条件基类：与当前 `updated_at` 不一致时返回 409 `SYNC_CONFLICT`。

    直接继承即可获得 `expected_updated_at` 字段（不要再叠加 BaseModel，避免 MRO 冲突）。
    """

    expected_updated_at: datetime | None = None
