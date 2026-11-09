from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import PyJWTError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User
from app.services import auth_service
from app.utils.storage import ensure_content_length

DbSession = Annotated[Session, Depends(get_db)]


def enforce_upload_content_length(request: Request) -> None:
    """上传预检（依赖层兜底）：Content-Length 超限抛 413 FILE_TOO_LARGE。

    主拦截由 `UploadGuardMiddleware` 在 body 解析前完成；这里作为直连路由的兜底。
    头缺失（chunked）或非法时跳过，仍由服务层 `ensure_upload_size` 读取后校验。
    """
    ensure_content_length(
        request.headers.get("content-length"), max_mb=get_settings().max_upload_mb
    )


# 供文件上传端点声明的依赖：必须在 `await file.read()` 之前生效
UploadSizeCheck = Annotated[None, Depends(enforce_upload_content_length)]

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

__all__ = [
    "CurrentUser",
    "DbSession",
    "UploadSizeCheck",
    "get_current_user",
    "get_db",
]
