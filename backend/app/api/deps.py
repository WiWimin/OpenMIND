from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import PyJWTError
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User
from app.services import auth_service

DbSession = Annotated[Session, Depends(get_db)]

_bearer_scheme = HTTPBearer(auto_error=False)


def _auth_required() -> AppError:
    return AppError("AUTH_REQUIRED", "未登录或凭证失效", http_status=401)


def get_current_user(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
) -> User:
    if credentials is None or not credentials.credentials:
        raise _auth_required()
    try:
        payload = decode_access_token(credentials.credentials)
    except PyJWTError:
        raise _auth_required() from None
    subject = payload.get("sub")
    user = auth_service.get_active_user(db, subject) if isinstance(subject, str) else None
    if user is None:
        raise _auth_required()
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]

__all__ = ["CurrentUser", "DbSession", "get_current_user", "get_db"]
