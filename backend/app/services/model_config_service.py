from __future__ import annotations

import logging
from dataclasses import dataclass
from urllib.parse import urlsplit

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
from app.schemas.model_config import (
    ModelConfigRead,
    ModelConfigWrite,
    ModelPurpose,
    ProviderModelsRead,
)

logger = logging.getLogger(__name__)

_PROBE_PRESERVED_CODES = {
    "MODEL_TIMEOUT",
    "RATE_LIMITED",
    "INTERNAL_ERROR",
    "MODEL_QUOTA_EXCEEDED",
}


def _safe_host(api_base: str) -> str:
    try:
        return urlsplit(api_base).hostname or "invalid"
    except ValueError:
        return "invalid"


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


def resolve_model_config(
    db: Session,
    user_id: str,
    *,
    purpose: ModelPurpose | None = None,
    model_override: str | None = None,
) -> ModelConfig:
    row = model_config_repository.get_by_user(db, user_id)
    settings = get_settings()
    llm_api_base = row.llm_api_base if row and row.llm_api_base else ""
    llm_api_key = _decrypt_or_empty(row.llm_api_key_enc if row else None)
    llm_model = row.llm_model if row and row.llm_model else ""
    # 向量模型收归服务端统一配置（docker/.env），用户侧不提供自备入口。
    embedding_api_base = settings.embedding_api_base
    embedding_api_key = settings.embedding_api_key
    embedding_model = settings.embedding_model
    embedding_dim = settings.embedding_dim

    # 回退开关仅作用于 LLM；Embedding 始终以服务端全局配置为准。
    if settings.allow_global_fallback:
        llm_api_base = llm_api_base or settings.llm_api_base
        llm_api_key = llm_api_key or settings.llm_api_key
        llm_model = llm_model or settings.llm_model

    if purpose is not None and row is not None:
        override = (row.llm_purpose_models or {}).get(purpose.value)
        if override:
            llm_model = override

    # 请求级模型覆盖：模型名由前端从服务商预设清单中选择，是否有效交由服务商 API 判定
    if model_override:
        llm_model = model_override

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
    return exc.message


def _probe_error(prefix: str, exc: AppError) -> AppError:
    message = f"{prefix} 校验失败：{_probe_message(exc)}"
    if exc.error_code in _PROBE_PRESERVED_CODES:
        return AppError(
            exc.error_code,
            message,
            http_status=exc.http_status,
            retryable=exc.retryable,
        )
    return AppError("MODEL_CONFIG_INVALID", message, http_status=400, retryable=False)


def _probe_llm(api_base: str, api_key: str, model: str) -> bool:
    """保存前真实调用一次 LLM 做连通性校验。

    返回是否完成调用验证；遇到 429 限流时视为密钥认证已通过，
    放行保存并返回 False（响应带 `llm_probe_verified=false`）。
    """
    client = LLMClient(api_base=api_base, api_key=api_key, model=model)
    try:
        client.probe()
    except AppError as exc:
        if exc.error_code == "RATE_LIMITED":
            logger.warning(
                "LLM 校验遇到限流，视为密钥有效放行保存 host=%s model=%s",
                _safe_host(api_base),
                model,
            )
            return False
        logger.warning(
            "LLM 校验失败 host=%s model=%s error_code=%s retryable=%s",
            _safe_host(api_base),
            model,
            exc.error_code,
            exc.retryable,
        )
        raise _probe_error("LLM", exc) from None
    return True


def save_model_config(
    db: Session, user_id: str, payload: ModelConfigWrite
) -> tuple[UserModelConfig, bool]:
    """保存 LLM BYOK 配置，返回（配置行, 是否完成调用验证）。

    向量模型不支持用户自备：仅接受 LLM 三字段，Embedding 由服务端
    `docker/.env` 统一配置，本函数不触碰任何 Embedding 存储。
    """
    settings = get_settings()
    llm_api_base = payload.llm_api_base
    llm_verified = True

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
        llm_verified = _probe_llm(llm_api_base, payload.llm_api_key, payload.llm_model)

    row = model_config_repository.upsert(
        db,
        user_id=user_id,
        llm_api_base=llm_api_base,
        llm_api_key_enc=encrypt(payload.llm_api_key) if payload.llm_api_key else None,
        llm_model=payload.llm_model,
    )
    return row, llm_verified


def list_provider_models(db: Session, user_id: str) -> ProviderModelsRead:
    """拉取用户当前 LLM 服务商的可用模型清单，供会话内模型选择器展示。"""
    config = resolve_model_config(db, user_id)
    if not (config.llm_api_base and config.llm_api_key and config.llm_model):
        raise AppError("MODEL_CONFIG_REQUIRED", "未配置大模型（LLM）", http_status=400)
    client = build_llm_client(config)
    models = client.list_models(timeout_s=10)
    return ProviderModelsRead(llm_model=config.llm_model, models=models)


def save_purpose_models(
    db: Session, user_id: str, models: dict[ModelPurpose, str]
) -> UserModelConfig:
    cleaned: dict[str, str] = {}
    for purpose, model in models.items():
        text = model.strip()
        if not text:
            raise AppError(
                "MODEL_CONFIG_INVALID", "用途模型名不能为空", http_status=400
            )
        if len(text) > 100:
            raise AppError(
                "MODEL_CONFIG_INVALID",
                "用途模型名不能超过 100 个字符",
                http_status=400,
            )
        cleaned[purpose.value] = text

    if cleaned:
        config = resolve_model_config(db, user_id)
        if not (config.llm_api_base and config.llm_api_key and config.llm_model):
            raise AppError(
                "MODEL_CONFIG_INVALID",
                "请先配置大模型，再设置用途模型",
                http_status=400,
            )

    return model_config_repository.update_purpose_models(
        db, user_id=user_id, models=cleaned
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
        None,
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
        llm_purpose_models=(row.llm_purpose_models or {}) if row else {},
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
