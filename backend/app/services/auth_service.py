from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.core.security import hash_password, verify_password
from app.models.user import User
from app.repositories import user_repository
from app.utils.ids import new_id

_ACTIVE_STATUS = "active"


def _auth_error() -> AppError:
    return AppError("AUTH_REQUIRED", "用户名或密码错误", http_status=401)


def register(db: Session, name: str, password: str) -> User:
    if user_repository.get_by_name(db, name) is not None:
        raise AppError(
            "BUSINESS_RULE_VIOLATION",
            "该用户名已被注册",
            http_status=409,
        )
    return user_repository.create(
        db,
        user_id=new_id("usr"),
        name=name,
        password_hash=hash_password(password),
    )


def authenticate(db: Session, name: str, password: str) -> User:
    user = user_repository.get_by_name(db, name)
    if user is None or not verify_password(password, user.password_hash):
        raise _auth_error()
    if user.status != _ACTIVE_STATUS:
        raise _auth_error()
    return user


def get_active_user(db: Session, user_id: str) -> User | None:
    user = user_repository.get_by_id(db, user_id)
    if user is None or user.status != _ACTIVE_STATUS:
        return None
    return user
