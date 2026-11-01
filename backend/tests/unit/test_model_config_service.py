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
    # Embedding 始终取服务端全局设置（不依赖用户行）
    settings = get_settings()
    assert config.embedding_api_base == settings.embedding_api_base
    assert config.embedding_api_key == settings.embedding_api_key
    assert config.embedding_model == settings.embedding_model
    assert config.embedding_dim == settings.embedding_dim


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


def test_resolve_embedding_always_from_settings(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """向量模型收归服务端：即使关闭全局回退，Embedding 也取全局配置。"""
    _make_user(db_session, "usr_a", "alice")
    base = get_settings()
    monkeypatch.setattr(
        model_config_service,
        "get_settings",
        lambda: base.model_copy(
            update={
                "embedding_api_base": "https://emb.example.com/v1",
                "embedding_api_key": "sk-global-emb",
                "embedding_model": "global-embedding",
                "embedding_dim": 1024,
                "allow_global_fallback": False,
            }
        ),
    )
    config = resolve_model_config(db_session, "usr_a")
    assert config.embedding_api_base == "https://emb.example.com/v1"
    assert config.embedding_api_key == "sk-global-emb"
    assert config.embedding_model == "global-embedding"
    assert config.embedding_dim == 1024
    # LLM 未配置且未开启回退，保持为空
    assert config.llm_api_base == ""


def test_resolve_prefers_user_llm_config(db_session: Session) -> None:
    _make_user(db_session, "usr_a", "alice")
    model_config_repository.upsert(
        db_session,
        user_id="usr_a",
        llm_api_base="https://llm.example.com",
        llm_api_key_enc=encrypt("user-llm-key"),
        llm_model="user-model",
    )
    config = resolve_model_config(db_session, "usr_a")
    assert config.llm_api_base == "https://llm.example.com"
    assert config.llm_api_key == "user-llm-key"
    assert config.llm_model == "user-model"


def test_resolve_applies_purpose_model_override(db_session: Session) -> None:
    _make_user(db_session, "usr_a", "alice")
    model_config_repository.upsert(
        db_session,
        user_id="usr_a",
        llm_api_base="https://llm.example.com",
        llm_api_key_enc=encrypt("user-llm-key"),
        llm_model="default-model",
        llm_purpose_models={"minutes": "minutes-model"},
    )

    minutes = resolve_model_config(
        db_session, "usr_a", purpose=model_config_service.ModelPurpose.minutes
    )
    chat = resolve_model_config(
        db_session, "usr_a", purpose=model_config_service.ModelPurpose.chat
    )

    assert minutes.llm_model == "minutes-model"
    assert chat.llm_model == "default-model"


def test_resolve_partial_user_config_keeps_llm_only(db_session: Session) -> None:
    _make_user(db_session, "usr_a", "alice")
    model_config_repository.upsert(
        db_session,
        user_id="usr_a",
        llm_api_base="https://llm.example.com",
        llm_api_key_enc=encrypt("key"),
        llm_model="m",
    )
    config = resolve_model_config(db_session, "usr_a")
    assert config.llm_api_base == "https://llm.example.com"
    # Embedding 不再来自用户配置行，而取服务端设置
    settings = get_settings()
    assert config.embedding_api_base == settings.embedding_api_base
    assert config.embedding_api_key == settings.embedding_api_key


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


def test_probe_llm_verified_when_probe_passes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(model_config_service.LLMClient, "probe", lambda self, **k: None)
    assert (
        model_config_service._probe_llm("https://llm.example.com/v1", "key", "model") is True
    )


def test_probe_llm_rate_limited_allows_save(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """429 限流说明密钥认证已通过，放行保存并返回未验证标志。"""

    def rate_limited(self, **kwargs):
        raise AppError("RATE_LIMITED", "模型服务限流", http_status=429, retryable=True)

    monkeypatch.setattr(model_config_service.LLMClient, "probe", rate_limited)
    assert (
        model_config_service._probe_llm("https://llm.example.com/v1", "key", "model") is False
    )


def test_probe_llm_preserves_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(self, **kwargs):
        raise AppError("MODEL_TIMEOUT", "模型调用超时", http_status=504, retryable=True)

    monkeypatch.setattr(model_config_service.LLMClient, "probe", fail)
    with pytest.raises(AppError) as exc_info:
        model_config_service._probe_llm("https://llm.example.com/v1", "key", "model")

    assert exc_info.value.error_code == "MODEL_TIMEOUT"
    assert exc_info.value.http_status == 504
    assert exc_info.value.retryable is True


def test_save_model_config_writes_llm_and_reports_verified(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core import url_validation

    monkeypatch.setattr(
        url_validation, "_resolve_host", lambda host, port: {"93.184.216.34"}
    )
    _make_user(db_session, "usr_a", "alice")
    monkeypatch.setattr(model_config_service.LLMClient, "probe", lambda self, **k: None)
    payload = model_config_service.ModelConfigWrite(
        llm_api_base="https://llm.example.com/v1",
        llm_api_key="sk-user",
        llm_model="user-model",
    )
    row, verified = model_config_service.save_model_config(db_session, "usr_a", payload)
    assert verified is True
    assert row.llm_model == "user-model"


def _make_config_row(db_session: Session) -> None:
    model_config_repository.upsert(
        db_session,
        user_id="usr_a",
        llm_api_base="https://llm.example.com",
        llm_api_key_enc=encrypt("user-llm-key"),
        llm_model="default-model",
        llm_purpose_models={"minutes": "minutes-model"},
    )


def test_model_override_accepts_registered_model(db_session: Session) -> None:
    _make_user(db_session, "usr_a", "alice")
    _make_config_row(db_session)
    for model in ("default-model", "minutes-model"):
        config = resolve_model_config(db_session, "usr_a", model_override=model)
        assert config.llm_model == model


def test_model_override_accepts_any_model_name(db_session: Session) -> None:
    """请求级模型覆盖不再校验登记列表，模型是否有效由服务商 API 判定。"""
    _make_user(db_session, "usr_a", "alice")
    _make_config_row(db_session)
    config = resolve_model_config(db_session, "usr_a", model_override="brand-new-model")
    assert config.llm_model == "brand-new-model"


def test_model_override_takes_priority_over_purpose(db_session: Session) -> None:
    _make_user(db_session, "usr_a", "alice")
    _make_config_row(db_session)
    config = resolve_model_config(
        db_session,
        "usr_a",
        purpose=model_config_service.ModelPurpose.minutes,
        model_override="default-model",
    )
    assert config.llm_model == "default-model"
