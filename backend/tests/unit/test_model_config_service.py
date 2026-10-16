from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.crypto import encrypt
from app.models.user import User
from app.repositories import model_config_repository
from app.services.model_config_service import resolve_model_config


def _make_user(db: Session, user_id: str, name: str) -> User:
    user = User(user_id=user_id, name=name, password_hash="x")
    db.add(user)
    db.commit()
    return user


def test_resolve_falls_back_to_global(db_session: Session) -> None:
    _make_user(db_session, "usr_a", "alice")
    config = resolve_model_config(db_session, "usr_a")
    settings = get_settings()
    assert config.llm_api_base == settings.llm_api_base
    assert config.llm_api_key == settings.llm_api_key
    assert config.embedding_dim == settings.embedding_dim


def test_resolve_prefers_user_config(db_session: Session) -> None:
    _make_user(db_session, "usr_a", "alice")
    model_config_repository.upsert(
        db_session,
        user_id="usr_a",
        llm_api_base="https://llm.example.com",
        llm_api_key_enc=encrypt("user-llm-key"),
        llm_model="user-model",
        embedding_api_base=None,
        embedding_api_key_enc=None,
        embedding_model=None,
        embedding_dim=None,
    )
    config = resolve_model_config(db_session, "usr_a")
    assert config.llm_api_base == "https://llm.example.com"
    assert config.llm_api_key == "user-llm-key"
    assert config.llm_model == "user-model"
    settings = get_settings()
    assert config.embedding_api_base == settings.embedding_api_base


def test_resolve_partial_user_config_keeps_global_embedding(db_session: Session) -> None:
    _make_user(db_session, "usr_a", "alice")
    model_config_repository.upsert(
        db_session,
        user_id="usr_a",
        llm_api_base="https://llm.example.com",
        llm_api_key_enc=encrypt("key"),
        llm_model="m",
        embedding_api_base="https://emb.example.com",
        embedding_api_key_enc=encrypt("emb-key"),
        embedding_model="emb-model",
        embedding_dim=1024,
    )
    config = resolve_model_config(db_session, "usr_a")
    assert config.embedding_api_base == "https://emb.example.com"
    assert config.embedding_api_key == "emb-key"
    assert config.embedding_dim == 1024
