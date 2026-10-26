import pytest
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.crypto import encrypt
from app.core.exceptions import AppError
from app.models.user import User
from app.repositories import model_config_repository
from app.services import model_config_service
from app.services.model_config_service import (
    ModelConfig,
    _provider_source,
    build_embedding_client,
    build_llm_client,
    resolve_model_config,
)


def _make_user(db: Session, user_id: str, name: str) -> User:
    user = User(user_id=user_id, name=name, password_hash="x")
    db.add(user)
    db.commit()
    return user


def _empty_config() -> ModelConfig:
    return ModelConfig("", "", "", "", "", "", 1024)


def test_resolve_no_config_returns_empty_by_default(db_session: Session) -> None:
    _make_user(db_session, "usr_a", "alice")
    config = resolve_model_config(db_session, "usr_a")
    assert config.llm_api_base == ""
    assert config.llm_api_key == ""
    assert config.llm_model == ""
    assert config.embedding_api_base == ""
    assert config.embedding_api_key == ""
    assert config.embedding_model == ""


def test_resolve_global_fallback_only_when_flag_enabled(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _make_user(db_session, "usr_a", "alice")
    base = get_settings()
    monkeypatch.setattr(
        model_config_service,
        "get_settings",
        lambda: base.model_copy(update={"allow_global_fallback": True}),
    )
    config = resolve_model_config(db_session, "usr_a")
    assert config.llm_api_base == base.llm_api_base
    assert config.llm_model == base.llm_model


def test_resolve_prefers_user_config(db_session: Session) -> None:
    _make_user(db_session, "usr_a", "alice")
    model_config_repository.upsert(
        db_session,
        user_id="usr_a",
        llm_api_base="https://llm.example.com",
        llm_api_key_enc=encrypt("user-llm-key"),
        llm_model="user-model",
        embedding_api_base="https://emb.example.com",
        embedding_api_key_enc=encrypt("emb-key"),
        embedding_model="emb-model",
        embedding_dim=1024,
    )
    config = resolve_model_config(db_session, "usr_a")
    assert config.llm_api_base == "https://llm.example.com"
    assert config.llm_api_key == "user-llm-key"
    assert config.llm_model == "user-model"
    assert config.embedding_api_base == "https://emb.example.com"
    assert config.embedding_dim == 1024


def test_resolve_partial_user_config_keeps_embedding_empty(db_session: Session) -> None:
    _make_user(db_session, "usr_a", "alice")
    model_config_repository.upsert(
        db_session,
        user_id="usr_a",
        llm_api_base="https://llm.example.com",
        llm_api_key_enc=encrypt("key"),
        llm_model="m",
        embedding_api_base=None,
        embedding_api_key_enc=None,
        embedding_model=None,
        embedding_dim=None,
    )
    config = resolve_model_config(db_session, "usr_a")
    assert config.llm_api_base == "https://llm.example.com"
    assert config.embedding_api_base == ""
    assert config.embedding_api_key == ""


def test_provider_source_priority() -> None:
    assert _provider_source("https://llm.example.com", "", "", "") == "user"
    assert _provider_source(None, "https://g/v1", "k", "m") == "global"
    assert _provider_source(None, "", "", "") == "none"
    assert _provider_source(None, "https://g/v1", "", "m") == "none"


def test_build_llm_unconfigured_chat_raises_model_config_required() -> None:
    client = build_llm_client(_empty_config())
    with pytest.raises(AppError) as exc_info:
        client.chat([{"role": "user", "content": "x"}])
    assert exc_info.value.error_code == "MODEL_CONFIG_REQUIRED"


def test_build_embedding_unconfigured_embed_raises_model_config_required() -> None:
    client = build_embedding_client(_empty_config())
    with pytest.raises(AppError) as exc_info:
        client.embed(["x"])
    assert exc_info.value.error_code == "MODEL_CONFIG_REQUIRED"


def test_build_llm_does_not_fall_back_to_global_when_empty() -> None:
    client = build_llm_client(_empty_config())
    assert client.api_base == ""
    assert client.api_key == ""


def test_build_embedding_does_not_fall_back_to_global_when_empty() -> None:
    client = build_embedding_client(_empty_config())
    assert client.api_base == ""
    assert client.api_key == ""
