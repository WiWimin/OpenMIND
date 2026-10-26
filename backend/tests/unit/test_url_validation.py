from __future__ import annotations

import pytest

from app.core import url_validation
from app.core.exceptions import AppError


@pytest.fixture(autouse=True)
def _public_dns(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        url_validation,
        "_resolve_host",
        lambda host, port: {"93.184.216.34"},
    )


def test_accepts_public_https_base() -> None:
    assert (
        url_validation.validate_api_base(
            "https://example.com/v1/", field="LLM API Base"
        )
        == "https://example.com/v1"
    )


def test_rejects_non_https_public_base() -> None:
    with pytest.raises(AppError) as exc_info:
        url_validation.validate_api_base("http://example.com/v1", field="LLM API Base")
    assert exc_info.value.error_code == "MODEL_CONFIG_INVALID"


def test_rejects_private_literal_ip() -> None:
    with pytest.raises(AppError):
        url_validation.validate_api_base("https://127.0.0.1/v1", field="LLM API Base")


def test_rejects_localhost_and_metadata_hosts() -> None:
    for base in (
        "https://localhost/v1",
        "https://metadata.google.internal/v1",
        "https://host.docker.internal/v1",
    ):
        with pytest.raises(AppError):
            url_validation.validate_api_base(base, field="LLM API Base")


def test_rejects_credentials_and_query() -> None:
    for base in (
        "https://user:pass@example.com/v1",
        "https://example.com/v1?token=secret",
    ):
        with pytest.raises(AppError):
            url_validation.validate_api_base(base, field="LLM API Base")


def test_rejects_hostname_resolving_to_private_ip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        url_validation,
        "_resolve_host",
        lambda host, port: {"10.0.0.8"},
    )
    with pytest.raises(AppError):
        url_validation.validate_api_base("https://example.com/v1", field="LLM API Base")


def test_rejects_unresolvable_host(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(host: str, port: int) -> set[str]:
        raise OSError("dns failure")

    monkeypatch.setattr(url_validation, "_resolve_host", fail)
    with pytest.raises(AppError):
        url_validation.validate_api_base("https://example.com/v1", field="LLM API Base")


def test_allow_private_permits_local_http_endpoint() -> None:
    assert (
        url_validation.validate_api_base(
            "http://127.0.0.1:8000/v1",
            field="LLM API Base",
            allow_private=True,
        )
        == "http://127.0.0.1:8000/v1"
    )
