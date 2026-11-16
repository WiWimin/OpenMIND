"""索引参数指纹与文件摘要：增量索引复用判定的两个依据。"""

from __future__ import annotations

from app.ai.indexing import build_index_fingerprint, file_sha256
from app.core.config import Settings


def _settings(**overrides) -> Settings:
    return Settings(_env_file=None, **overrides)


def test_file_sha256_stable_and_content_sensitive() -> None:
    assert file_sha256(b"abc") == file_sha256(b"abc")
    assert file_sha256(b"abc") != file_sha256(b"abd")
    assert len(file_sha256(b"abc")) == 64


def test_fingerprint_stable_for_same_environment() -> None:
    assert build_index_fingerprint(_settings()) == build_index_fingerprint(_settings())


def test_fingerprint_changes_with_embedding_model() -> None:
    base = build_index_fingerprint(_settings(embedding_model="a"))
    assert base != build_index_fingerprint(_settings(embedding_model="b"))


def test_fingerprint_changes_with_embedding_dim() -> None:
    base = build_index_fingerprint(_settings(embedding_dim=1024))
    assert base != build_index_fingerprint(_settings(embedding_dim=512))


def test_fingerprint_changes_with_chunk_params() -> None:
    base = build_index_fingerprint(_settings())
    assert base != build_index_fingerprint(_settings(rag_chunk_size=500))
    assert base != build_index_fingerprint(_settings(rag_chunk_overlap=60))


def test_fingerprint_changes_with_fingerprint_version() -> None:
    base = build_index_fingerprint(_settings(rag_index_fingerprint_version=1))
    assert base != build_index_fingerprint(_settings(rag_index_fingerprint_version=2))
