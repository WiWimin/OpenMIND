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
