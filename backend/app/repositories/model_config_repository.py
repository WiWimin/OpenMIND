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
    embedding_api_base: str | None,
    embedding_api_key_enc: str | None,
    embedding_model: str | None,
    embedding_dim: int | None,
) -> UserModelConfig:
    config = db.get(UserModelConfig, user_id)
    if config is None:
        config = UserModelConfig(user_id=user_id)
        db.add(config)
    config.llm_api_base = llm_api_base
    config.llm_api_key_enc = llm_api_key_enc
    config.llm_model = llm_model
    config.embedding_api_base = embedding_api_base
    config.embedding_api_key_enc = embedding_api_key_enc
    config.embedding_model = embedding_model
    config.embedding_dim = embedding_dim
    db.commit()
    db.refresh(config)
    return config


def delete(db: Session, config: UserModelConfig) -> None:
    db.delete(config)
    db.commit()
