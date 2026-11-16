from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_development_allows_default_secret_key() -> None:
    settings = Settings(_env_file=None, app_env="development", secret_key="change-me")
    assert settings.secret_key == "change-me"


def test_production_rejects_weak_secret_key() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, app_env="production", secret_key="change-me")


def test_staging_rejects_short_secret_key() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, app_env="staging", secret_key="too-short")


def test_production_accepts_strong_secret_key() -> None:
    settings = Settings(_env_file=None, app_env="production", secret_key="a" * 64)
    assert settings.secret_key == "a" * 64


def test_previous_secret_key_is_optional() -> None:
    settings = Settings(
        _env_file=None,
        app_env="production",
        secret_key="a" * 64,
        secret_key_previous="old-secret",
    )
    assert settings.secret_key_previous == "old-secret"


# ---------- CORS 白名单校验 ----------


def test_cors_defaults_to_single_origin() -> None:
    settings = Settings(_env_file=None)
    assert settings.cors_origin_list == ["http://localhost:5173"]


def test_cors_supports_multiple_origins_and_normalizes() -> None:
    settings = Settings(
        _env_file=None,
        cors_origins="http://localhost:5173/, https://openmind.example.com , http://localhost:5173",
    )
    assert settings.cors_origin_list == [
        "http://localhost:5173",
        "https://openmind.example.com",
    ]


def test_cors_rejects_wildcard() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, cors_origins="*")


def test_cors_rejects_origin_with_path() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, cors_origins="http://localhost:5173/app")


def test_cors_rejects_non_http_scheme() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, cors_origins="ftp://files.example.com")


def test_cors_rejects_query_and_fragment() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, cors_origins="http://localhost:5173?x=1")


def test_cors_rejects_empty_list() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, cors_origins="  ,  ")


# ---------- RAG 参数校验 ----------


def test_rag_defaults_match_historical_behavior() -> None:
    settings = Settings(_env_file=None)
    assert settings.rag_chunk_size == 800
    assert settings.rag_chunk_overlap == 120
    assert settings.rag_top_k == 5
    assert settings.rag_min_score == 0.3
    assert settings.rag_vector_backend == "auto"
    assert settings.rag_incremental_index_enabled is True


def test_rag_rejects_overlap_not_less_than_chunk_size() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, rag_chunk_size=100, rag_chunk_overlap=100)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, rag_chunk_size=100, rag_chunk_overlap=120)


def test_rag_rejects_negative_overlap() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, rag_chunk_overlap=-1)


def test_rag_rejects_invalid_min_score() -> None:
    for value in (-0.1, 1.1):
        with pytest.raises(ValidationError):
            Settings(_env_file=None, rag_min_score=value)


def test_rag_rejects_non_positive_top_k_and_oversample() -> None:
    for field in ("rag_top_k", "rag_ann_oversample", "rag_ann_max_candidates"):
        with pytest.raises(ValidationError):
            Settings(_env_file=None, **{field: 0})


def test_rag_rejects_unknown_vector_backend() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, rag_vector_backend="faiss")


def test_rag_accepts_explicit_vector_backends() -> None:
    for backend in ("auto", "python", "pgvector"):
        settings = Settings(_env_file=None, rag_vector_backend=backend)
        assert settings.rag_vector_backend == backend
