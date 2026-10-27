from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, MultiFernet

from app.core.config import get_settings


def _build_fernet(secret: str) -> Fernet:
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def _fernet() -> MultiFernet:
    settings = get_settings()
    keys = [_build_fernet(settings.secret_key)]
    previous = settings.secret_key_previous.strip()
    if previous and previous != settings.secret_key:
        keys.append(_build_fernet(previous))
    return MultiFernet(keys)


def encrypt(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt(token: str) -> str:
    return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
