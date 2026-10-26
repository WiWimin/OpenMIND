from __future__ import annotations

from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_WEAK_SECRET_KEYS = {
    "",
    "change-me",
    "changeme",
    "secret",
    "your-secret",
    "your-secret-key",
    "dev-secret",
    "test-secret",
}
_LOCAL_APP_ENVS = {"development", "dev", "test"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../docker/.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "OpenMIND"
    app_env: str = "development"
    api_v1_prefix: str = "/api/v1"
    secret_key: str = "change-me"
    secret_key_previous: str = ""
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "openmind"
    postgres_password: str = "change-me"
    postgres_db: str = "openmind"
    database_url: str = "postgresql+psycopg://openmind:change-me@localhost:5432/openmind"

    storage_dir: str = "./storage"
    max_upload_mb: int = 20

    cors_origins: str = "http://localhost:5173"

    llm_api_base: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    embedding_api_base: str = ""
    embedding_api_key: str = ""
    embedding_model: str = ""
    embedding_dim: int = 1024
    asr_api_base: str = ""
    asr_api_key: str = ""
    asr_model: str = ""
    allow_global_fallback: bool = False
    allow_private_model_endpoints: bool = False

    @model_validator(mode="after")
    def _validate_secret_key(self) -> Settings:
        normalized = self.secret_key.strip().lower()
        weak = normalized in _WEAK_SECRET_KEYS or len(self.secret_key) < 32
        if weak and self.app_env.strip().lower() not in _LOCAL_APP_ENVS:
            raise ValueError(
                "SECRET_KEY 必须设置为至少 32 字符的随机值，且不能使用默认占位值"
            )
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
