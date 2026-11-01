from __future__ import annotations

import shutil
from pathlib import Path


def _resolve(storage_dir: str, relative_key: str) -> Path:
    return Path(storage_dir).resolve() / relative_key


def save_bytes(storage_dir: str, *, relative_key: str, data: bytes) -> None:
    path = _resolve(storage_dir, relative_key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def read_bytes(storage_dir: str, relative_key: str) -> bytes:
    return _resolve(storage_dir, relative_key).read_bytes()


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
