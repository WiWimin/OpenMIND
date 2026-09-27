from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


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
    embedding_dim: int = 1536

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
