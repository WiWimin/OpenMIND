from datetime import timedelta

import pytest
from jwt.exceptions import ExpiredSignatureError

from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_hash_roundtrip() -> None:
    hashed = hash_password("secret123")
    assert hashed != "secret123"
    assert verify_password("secret123", hashed)
    assert not verify_password("wrong-password", hashed)


def test_access_token_roundtrip() -> None:
    token = create_access_token("usr_abc")
    payload = decode_access_token(token)
    assert payload["sub"] == "usr_abc"
    assert "exp" in payload


def test_access_token_expired() -> None:
    token = create_access_token("usr_abc", expires_delta=timedelta(seconds=-1))
    with pytest.raises(ExpiredSignatureError):
        decode_access_token(token)
