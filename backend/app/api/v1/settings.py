from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.schemas.common import Envelope
from app.schemas.model_config import (
    ModelConfigDeleteResult,
    ModelConfigRead,
    ModelConfigWrite,
)
from app.services import model_config_service

router = APIRouter(tags=["settings"])


@router.get("/me/settings/model", response_model=Envelope[ModelConfigRead])
def get_model_config(db: DbSession, current_user: CurrentUser) -> Envelope[ModelConfigRead]:
    data = model_config_service.get_model_config_read(db, current_user.user_id)
    return Envelope(data=data)


@router.put("/me/settings/model", response_model=Envelope[ModelConfigRead])
def put_model_config(
    payload: ModelConfigWrite, db: DbSession, current_user: CurrentUser
) -> Envelope[ModelConfigRead]:
    model_config_service.save_model_config(db, current_user.user_id, payload)
    data = model_config_service.get_model_config_read(db, current_user.user_id)
    return Envelope(data=data)


@router.delete(
    "/me/settings/model", response_model=Envelope[ModelConfigDeleteResult]
)
def delete_model_config(
    db: DbSession, current_user: CurrentUser
) -> Envelope[ModelConfigDeleteResult]:
    model_config_service.clear_model_config(db, current_user.user_id)
    return Envelope(data=ModelConfigDeleteResult())
