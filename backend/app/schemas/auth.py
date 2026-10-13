from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=6, max_length=128)


class LoginRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=128)


class AuthUser(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: str
    name: str
    created_at: datetime


class AuthSession(BaseModel):
    user: AuthUser
    access_token: str
    token_type: str = "bearer"


class LogoutResult(BaseModel):
    logged_out: bool = True
