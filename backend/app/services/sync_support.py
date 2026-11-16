"""本地工作区双向同步的服务端支撑：乐观锁与幂等键（docs/api.md 一.3）。

- 乐观锁：PATCH 携带 `expected_updated_at` / `expected_version`，不一致返回 409 `SYNC_CONFLICT`；
- 幂等键：创建携带 `client_op_id`，重复提交返回已有实体，内容不同返回 409 `IDEMPOTENCY_KEY_REUSED`。
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.core.exceptions import AppError


def _normalize(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _iso(value: datetime | None) -> str | None:
    normalized = _normalize(value)
    return normalized.isoformat() if normalized else None


def ensure_unmodified(
    current: datetime | None,
    expected: datetime | None,
    *,
    label: str = "内容",
    current_version: int | None = None,
) -> None:
    """乐观锁：`expected` 与当前更新时间不一致时抛 409 SYNC_CONFLICT。"""
    if expected is None:
        return
    if _normalize(current) != _normalize(expected):
        details: dict[str, object] = {
            "current_updated_at": _iso(current),
            "expected_updated_at": _iso(expected),
        }
        if current_version is not None:
            details["current_version"] = current_version
        raise AppError(
            "SYNC_CONFLICT",
            f"{label}已被其他操作修改，请先比对后重试",
            http_status=409,
            details=details,
        )


def ensure_version(current_version: int, expected_version: int | None) -> None:
    """乐观锁：纪要以 `version` 作为前置条件。"""
    if expected_version is None:
        return
    if current_version != expected_version:
        raise AppError(
            "SYNC_CONFLICT",
            "纪要已被其他操作修改，请先比对后重试",
            http_status=409,
            details={
                "current_version": current_version,
                "expected_version": expected_version,
            },
        )


def ensure_same_payload(
    existing: dict[str, object],
    incoming: dict[str, object],
) -> None:
    """幂等键冲突：同一 `client_op_id` 携带了不同内容时抛 409 IDEMPOTENCY_KEY_REUSED。"""
    if existing != incoming:
        raise AppError(
            "IDEMPOTENCY_KEY_REUSED",
            "client_op_id 已用于不同的请求内容",
            http_status=409,
        )
