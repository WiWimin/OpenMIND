from __future__ import annotations

import shutil
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

from app.core.exceptions import AppError

_T = TypeVar("_T")

# multipart 边界/头部开销，避免恰好等于上限的合法文件被预检误拒
_CONTENT_LENGTH_OVERHEAD_BYTES = 8 * 1024


def _resolve(storage_dir: str, relative_key: str) -> Path:
    return Path(storage_dir).resolve() / relative_key


def ensure_upload_size(data: bytes, *, max_mb: int) -> None:
    """统一的上传大小校验：超过 `max_mb` 时抛 FILE_TOO_LARGE（413）。"""
    max_bytes = max_mb * 1024 * 1024
    if len(data) > max_bytes:
        raise AppError(
            "FILE_TOO_LARGE",
            f"文件超过大小限制（{max_mb}MB）",
            http_status=413,
        )


def ensure_content_length(content_length: str | None, *, max_mb: int) -> None:
    """上传预检：读取 body 之前用 Content-Length 拦截超大请求（413 FILE_TOO_LARGE）。

    头缺失（chunked）或非法时跳过，仍由 `ensure_upload_size` 读取后兜底。
    """
    if not content_length:
        return
    try:
        declared = int(content_length)
    except ValueError:
        return
    if declared > max_mb * 1024 * 1024 + _CONTENT_LENGTH_OVERHEAD_BYTES:
        raise AppError(
            "FILE_TOO_LARGE",
            f"文件超过大小限制（{max_mb}MB）",
            http_status=413,
        )


def save_then_create(
    storage_dir: str, relative_key: str, data: bytes, create: Callable[[], _T]
) -> _T:
    """「先落盘 → 再建库」的统一补偿模式：建库失败时删除已写入的文件后原样抛出。"""
    save_bytes(storage_dir, relative_key=relative_key, data=data)
    try:
        return create()
    except Exception:
        delete_object(storage_dir, relative_key)
        raise


def save_bytes(storage_dir: str, *, relative_key: str, data: bytes) -> None:
    path = _resolve(storage_dir, relative_key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def read_bytes(storage_dir: str, relative_key: str) -> bytes:
    return _resolve(storage_dir, relative_key).read_bytes()


def stat_size(storage_dir: str, relative_key: str) -> int | None:
    """原始文件大小；文件不存在或不可访问时返回 None（供列表接口展示）。"""
    try:
        return _resolve(storage_dir, relative_key).stat().st_size
    except OSError:
        return None


def delete_object(storage_dir: str, relative_key: str) -> None:
    try:
        _resolve(storage_dir, relative_key).unlink()
    except FileNotFoundError:
        pass


def remove_tree(storage_dir: str, relative_key: str) -> None:
    """删除相对键对应的目录（若存在）；用于清理实时会话的分片目录。"""
    path = _resolve(storage_dir, relative_key)
    if path.is_dir():
        shutil.rmtree(path, ignore_errors=True)
