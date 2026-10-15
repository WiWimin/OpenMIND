from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet

from app.core.config import get_settings


def _fernet() -> Fernet:
    digest = hashlib.sha256(get_settings().secret_key.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt(token: str) -> str:
    return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
