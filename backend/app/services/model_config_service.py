from __future__ import annotations

from dataclasses import dataclass

from cryptography.fernet import InvalidToken
from sqlalchemy.orm import Session

from app.ai.embeddings import EmbeddingClient
from app.ai.llm import LLMClient
from app.core.config import get_settings
from app.core.crypto import decrypt, encrypt
from app.core.exceptions import AppError
from app.core.url_validation import validate_api_base
from app.models.model_config import UserModelConfig
from app.repositories import model_config_repository
from app.schemas.model_config import ModelConfigRead, ModelConfigWrite

EMBEDDING_DIM = 1024


@dataclass(frozen=True)
class ModelConfig:
    llm_api_base: str
    llm_api_key: str
    llm_model: str
    embedding_api_base: str
    embedding_api_key: str
    embedding_model: str
    embedding_dim: int


def _decrypt_or_empty(token: str | None) -> str:
    if not token:
        return ""
    try:
        return decrypt(token)
    except InvalidToken:
        raise AppError(
            "MODEL_CONFIG_INVALID",
            "模型密钥无法解密，请重新保存模型配置",
            http_status=400,
        ) from None


def resolve_model_config(db: Session, user_id: str) -> ModelConfig:
    settings = get_settings()
    row = model_config_repository.get_by_user(db, user_id)
    llm_api_base = (row.llm_api_base if row and row.llm_api_base else "") or settings.llm_api_base
    llm_api_key = _decrypt_or_empty(row.llm_api_key_enc if row else None) or settings.llm_api_key
    llm_model = (row.llm_model if row and row.llm_model else "") or settings.llm_model
    embedding_api_base = (
        (row.embedding_api_base if row and row.embedding_api_base else "")
        or settings.embedding_api_base
    )
    embedding_api_key = (
        _decrypt_or_empty(row.embedding_api_key_enc if row else None)
        or settings.embedding_api_key
    )
    embedding_model = (
        (row.embedding_model if row and row.embedding_model else "") or settings.embedding_model
    )
    embedding_dim = (
        (row.embedding_dim if row and row.embedding_dim else None) or settings.embedding_dim
    )
    return ModelConfig(
        llm_api_base=llm_api_base,
        llm_api_key=llm_api_key,
        llm_model=llm_model,
        embedding_api_base=embedding_api_base,
        embedding_api_key=embedding_api_key,
        embedding_model=embedding_model,
        embedding_dim=embedding_dim,
    )


def build_llm_client(config: ModelConfig) -> LLMClient:
    return LLMClient(
        api_base=config.llm_api_base,
        api_key=config.llm_api_key,
        model=config.llm_model,
    )


def build_embedding_client(config: ModelConfig) -> EmbeddingClient:
    return EmbeddingClient(
        api_base=config.embedding_api_base,
        api_key=config.embedding_api_key,
        model=config.embedding_model,
        dim=config.embedding_dim,
    )


def mask_key(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 7:
        return "***"
    return f"{key[:3]}...{key[-4:]}"


def _provider_source(
    user_value: str | None,
    effective_base: str,
    effective_key: str,
    effective_model: str,
) -> str:
    """判定某提供方的生效来源：user（用户自备）> global（服务端全局）> none。"""
    if user_value:
        return "user"
    if effective_base and effective_key and effective_model:
        return "global"
    return "none"


def _probe_message(exc: AppError) -> str:
    if exc.error_code == "MODEL_TIMEOUT":
        return "服务超时"
    if exc.error_code == "RATE_LIMITED":
        return "服务限流"
    if "维度" in exc.message:
        return f"向量维度必须为 {EMBEDDING_DIM}"
    if "未配置" in exc.message:
        return "缺少必要配置"
    return exc.message


def _probe_embedding_dim(api_base: str, api_key: str, model: str) -> None:
    client = EmbeddingClient(api_base=api_base, api_key=api_key, model=model, dim=EMBEDDING_DIM)
    try:
        vectors = client.embed(["OpenMIND 连通性测试"])
    except AppError as exc:
        raise AppError(
            "MODEL_CONFIG_INVALID",
            f"Embedding 校验失败：{_probe_message(exc)}",
            http_status=400,
        ) from None
    if not vectors:
        raise AppError("MODEL_CONFIG_INVALID", "Embedding 未返回向量", http_status=400)


def _probe_llm(api_base: str, api_key: str, model: str) -> None:
    client = LLMClient(api_base=api_base, api_key=api_key, model=model)
    try:
        client.chat(
            [{"role": "user", "content": "请只回复：正常"}],
            max_tokens=32,
            temperature=0,
            timeout_s=30,
        )
    except AppError as exc:
        raise AppError(
            "MODEL_CONFIG_INVALID",
            f"LLM 校验失败：{_probe_message(exc)}",
            http_status=400,
        ) from None


def save_model_config(db: Session, user_id: str, payload: ModelConfigWrite) -> UserModelConfig:
    settings = get_settings()
    llm_api_base = payload.llm_api_base
    embedding_api_base = payload.embedding_api_base

    if payload.embedding_api_base or payload.embedding_api_key or payload.embedding_model:
        if not (
            payload.embedding_api_base and payload.embedding_api_key and payload.embedding_model
        ):
            raise AppError(
                "MODEL_CONFIG_INVALID",
                "Embedding 需同时提供 api_base、api_key、model",
                http_status=400,
            )
        embedding_api_base = validate_api_base(
            payload.embedding_api_base,
            field="Embedding API Base",
            allow_private=settings.allow_private_model_endpoints,
        )
        _probe_embedding_dim(
            embedding_api_base, payload.embedding_api_key, payload.embedding_model
        )
    if payload.llm_api_base or payload.llm_api_key or payload.llm_model:
        if not (payload.llm_api_base and payload.llm_api_key and payload.llm_model):
            raise AppError(
                "MODEL_CONFIG_INVALID",
                "LLM 需同时提供 api_base、api_key、model",
                http_status=400,
            )
        llm_api_base = validate_api_base(
            payload.llm_api_base,
            field="LLM API Base",
            allow_private=settings.allow_private_model_endpoints,
        )
        _probe_llm(llm_api_base, payload.llm_api_key, payload.llm_model)

    return model_config_repository.upsert(
        db,
        user_id=user_id,
        llm_api_base=llm_api_base,
        llm_api_key_enc=encrypt(payload.llm_api_key) if payload.llm_api_key else None,
        llm_model=payload.llm_model,
        embedding_api_base=embedding_api_base,
        embedding_api_key_enc=(
            encrypt(payload.embedding_api_key) if payload.embedding_api_key else None
        ),
        embedding_model=payload.embedding_model,
        embedding_dim=(
            EMBEDDING_DIM if (payload.embedding_api_base or payload.embedding_model) else None
        ),
    )


def get_model_config_read(db: Session, user_id: str) -> ModelConfigRead:
    row = model_config_repository.get_by_user(db, user_id)
    config = resolve_model_config(db, user_id)
    llm_source = _provider_source(
        row.llm_api_base if row else None,
        config.llm_api_base,
        config.llm_api_key,
        config.llm_model,
    )
    embedding_source = _provider_source(
        row.embedding_api_base if row else None,
        config.embedding_api_base,
        config.embedding_api_key,
        config.embedding_model,
    )
    return ModelConfigRead(
        llm_api_base=config.llm_api_base,
        llm_model=config.llm_model,
        llm_api_key_masked=(
            mask_key(config.llm_api_key) if llm_source == "user" else ""
        ),
        llm_source=llm_source,
        embedding_api_base=config.embedding_api_base,
        embedding_model=config.embedding_model,
        embedding_api_key_masked=(
            mask_key(config.embedding_api_key) if embedding_source == "user" else ""
        ),
        embedding_source=embedding_source,
        embedding_dim=config.embedding_dim,
    )


def clear_model_config(db: Session, user_id: str) -> None:
    row = model_config_repository.get_by_user(db, user_id)
    if row is not None:
        model_config_repository.delete(db, row)
