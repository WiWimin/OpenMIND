from __future__ import annotations

from functools import lru_cache

from pydantic import field_validator, model_validator
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
    # 运维指标端点开关：关闭时 /api/v1/metrics 返回 404（隐藏端点存在性）
    metrics_enabled: bool = True

    # 限流（进程内滑动窗口；多 worker / 多实例下不共享，仅单实例有效）
    rate_limit_enabled: bool = True
    rate_limit_default_per_minute: int = 120
    rate_limit_login_per_minute: int = 10
    rate_limit_ai_per_minute: int = 20
    # 是否信任 X-Forwarded-For 计算客户端 IP（仅在受信反向代理后开启）
    trust_proxy_headers: bool = False
    rate_limit_max_keys: int = 10000

    llm_api_base: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    embedding_api_base: str = ""
    embedding_api_key: str = ""
    embedding_model: str = ""
    embedding_dim: int = 1024
    # RAG 相关性 Judge：top1 分数低于 rag_judge_min_score 时交 LLM 复核，
    # 判定“答不了”则整体拒答（拦截分数够但无关的负样本）；Judge 不可用时回退分数判定
    rag_judge_enabled: bool = True
    rag_judge_min_score: float = 0.6
    # RAG 检索性能告警（阈值告警日志，logger.error 行由日志收集侧捕获）：
    # 窗口 P95 超阈值时告警一次，冷却期内不重复；<=0 表示关闭该告警
    rag_alert_total_ms_p95: float = 3000.0
    rag_alert_candidate_rows_p95: float = 5000.0
    rag_alert_cooldown_s: float = 60.0
    # 联网检索（答案层后置补救）：资料无证据时先告知再联网作答；
    # 只影响答案层，不改变检索层阈值/Judge 口径；评测固定关闭
    web_search_enabled: bool = True
    web_search_provider: str = "bing"  # bing（本环境可达）| ddg
    web_search_max_results: int = 5
    web_search_timeout_s: float = 10.0
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

    @field_validator("cors_origins", mode="after")
    @classmethod
    def _validate_cors_origins(cls, value: str) -> str:
        """CORS 白名单校验：禁止 `*`，每个源必须是规范的 http/https origin。"""
        from urllib.parse import urlsplit

        normalized: list[str] = []
        for raw in value.split(","):
            origin = raw.strip()
            if not origin:
                continue
            if origin == "*":
                raise ValueError("CORS_ORIGINS 不允许使用通配符 *")
            parts = urlsplit(origin)
            if parts.scheme not in {"http", "https"}:
                raise ValueError(f"CORS_ORIGINS 源非法（scheme 必须是 http/https）：{origin}")
            if not parts.hostname:
                raise ValueError(f"CORS_ORIGINS 源非法（缺少 host）：{origin}")
            if parts.path not in ("", "/"):
                raise ValueError(f"CORS_ORIGINS 源非法（不允许包含路径）：{origin}")
            if parts.query or parts.fragment:
                raise ValueError(f"CORS_ORIGINS 源非法（不允许包含 query/fragment）：{origin}")
            # 去尾斜杠后归一化，避免同源因写法差异被重复或漏配
            origin = f"{parts.scheme}://{parts.netloc}"
            if origin not in normalized:
                normalized.append(origin)
        if not normalized:
            raise ValueError("CORS_ORIGINS 至少需要配置一个源")
        return ",".join(normalized)

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
