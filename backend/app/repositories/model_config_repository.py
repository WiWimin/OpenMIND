from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.model_config import UserModelConfig


def get_by_user(db: Session, user_id: str) -> UserModelConfig | None:
    return db.get(UserModelConfig, user_id)


def upsert(
    db: Session,
    *,
    user_id: str,
    llm_api_base: str | None,
    llm_api_key_enc: str | None,
    llm_model: str | None,
    llm_purpose_models: dict[str, str] | None = None,
) -> UserModelConfig:
    config = db.get(UserModelConfig, user_id)
    if config is None:
        config = UserModelConfig(user_id=user_id)
        db.add(config)
    config.llm_api_base = llm_api_base
    config.llm_api_key_enc = llm_api_key_enc
    config.llm_model = llm_model
    if llm_purpose_models is not None:
        config.llm_purpose_models = llm_purpose_models
    db.commit()
    db.refresh(config)
    return config


def update_purpose_models(
    db: Session, *, user_id: str, models: dict[str, str]
) -> UserModelConfig:
    config = db.get(UserModelConfig, user_id)
    if config is None:
        config = UserModelConfig(user_id=user_id)
        db.add(config)
    config.llm_purpose_models = models
    db.commit()
    db.refresh(config)
    return config


def delete(db: Session, config: UserModelConfig) -> None:
    db.delete(config)
    db.commit()
