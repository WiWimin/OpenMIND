from types import SimpleNamespace

import pytest
from cryptography.fernet import InvalidToken

from app.core import crypto
from app.core.crypto import decrypt, encrypt


def test_encrypt_decrypt_roundtrip() -> None:
    secret = "sk-test-1234567890"
    token = encrypt(secret)
    assert token != secret
    assert "sk-test" not in token
    assert decrypt(token) == secret


def test_encrypt_is_nondeterministic() -> None:
    assert encrypt("same-secret") != encrypt("same-secret")


def test_decrypt_preserves_unicode() -> None:
    value = "密钥-测试-🔐"
    assert decrypt(encrypt(value)) == value


def test_previous_key_can_decrypt_old_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        crypto,
        "get_settings",
        lambda: SimpleNamespace(secret_key="old-secret", secret_key_previous=""),
    )
    old_token = crypto.encrypt("old-value")

    monkeypatch.setattr(
        crypto,
        "get_settings",
        lambda: SimpleNamespace(
            secret_key="new-secret",
            secret_key_previous="old-secret",
        ),
    )
    assert crypto.decrypt(old_token) == "old-value"

    new_token = crypto.encrypt("new-value")
    monkeypatch.setattr(
        crypto,
        "get_settings",
        lambda: SimpleNamespace(secret_key="new-secret", secret_key_previous=""),
    )
    assert crypto.decrypt(new_token) == "new-value"

    monkeypatch.setattr(
        crypto,
        "get_settings",
        lambda: SimpleNamespace(secret_key="old-secret", secret_key_previous=""),
    )
    with pytest.raises(InvalidToken):
        crypto.decrypt(new_token)
