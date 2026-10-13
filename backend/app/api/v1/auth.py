from __future__ import annotations

from fastapi import APIRouter, status

from app.api.deps import CurrentUser, DbSession
from app.core.security import create_access_token
from app.models.user import User
from app.schemas.auth import (
    AuthSession,
    AuthUser,
    LoginRequest,
    LogoutResult,
    RegisterRequest,
)
from app.schemas.common import Envelope
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


def _build_session(user: User) -> AuthSession:
    return AuthSession(
        user=AuthUser.model_validate(user),
        access_token=create_access_token(user.user_id),
        token_type="bearer",
    )


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    response_model=Envelope[AuthSession],
)
def register(payload: RegisterRequest, db: DbSession) -> Envelope[AuthSession]:
    user = auth_service.register(db, payload.name, payload.password)
    return Envelope(data=_build_session(user))


@router.post("/login", response_model=Envelope[AuthSession])
def login(payload: LoginRequest, db: DbSession) -> Envelope[AuthSession]:
    user = auth_service.authenticate(db, payload.name, payload.password)
    return Envelope(data=_build_session(user))


@router.post("/logout", response_model=Envelope[LogoutResult])
def logout() -> Envelope[LogoutResult]:
    return Envelope(data=LogoutResult())


@router.get("/me", response_model=Envelope[AuthUser])
def me(current_user: CurrentUser) -> Envelope[AuthUser]:
    return Envelope(data=AuthUser.model_validate(current_user))
