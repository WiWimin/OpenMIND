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

    # 异步长任务（ADR-3：async_jobs + BackgroundTasks，无 Celery/Redis）。
    # 关闭时 5 个长任务入口走原同步逻辑（回滚开关）；单实例有效，进程重启丢 pending 任务
    # （启动 reap_stale + 读取懒回收兜底为 failed JOB_TIMEOUT）
    async_jobs_enabled: bool = True
    async_job_stale_minutes: int = 30

    # SSE 流式问答（ADR-1）：关闭时 /chat/stream 返回 404，前端回退同步 /chat
    sse_chat_enabled: bool = True
    # 心跳间隔（秒）：无增量时发送 `: ping` 注释行，<=0 关闭心跳
    sse_heartbeat_seconds: int = 15

    # Agent 框架（轻量工作流，不引入 LangGraph）。
    # AGENT_ENABLED=false 时 /agent/* 返回 404，前端回退既有页面链路（回滚开关）。
    agent_enabled: bool = True
    # 意图路由 LLM 兜底：关闭后只走规则 + 页面先验（成本更低，但歧义句退化）
    agent_intent_llm_enabled: bool = True
    agent_intent_llm_timeout_s: float = 3.0
    # 转写确认后自动生成纪要草稿（只落 draft，绝不自动确认）
    agent_auto_minutes_enabled: bool = True
    # 自动纪要同时抽取行动项（落 pending_confirmation）
    agent_auto_action_items_enabled: bool = False
    # 无证据联网前先请求用户确认（隐私优先）；关闭后恢复自动联网
    web_search_require_confirmation: bool = True
    # 待确认动作有效期（分钟）：过期后批准/拒绝返回 409
    agent_pending_action_ttl_minutes: int = 60
    # 会话保留天数：<=0 表示不自动清理
    agent_session_retention_days: int = 90
    # 单轮工作流预算
    agent_max_steps: int = 20
    agent_max_wall_seconds: float = 600.0

    # 持久化任务队列（DB 队列 + 独立 worker，无 Redis/Celery）。
    # JOB_WORKER_ENABLED=false 时仍由 API 进程 BackgroundTasks 执行（旧行为）。
    job_worker_enabled: bool = True
    job_worker_poll_seconds: float = 1.0
    job_worker_concurrency: int = 2
    job_max_attempts: int = 3

    llm_api_base: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    # AI 调用连接池：按 api_base 进程内复用 httpx 客户端（详见 ai/connection.py）
    ai_connection_pool_enabled: bool = True
    ai_max_connections: int = 20
    ai_max_keepalive_connections: int = 10
    ai_keepalive_expiry_s: float = 30.0
    # LLM 非幂等调用的全局 deadline（单次超时取 min(单次超时, 剩余预算)），<=0 关闭
    ai_call_deadline_s: float = 90.0
    # 并发闸门与熔断（ai/resilience.py）：单实例进程内状态，false 时全部直通
    ai_resilience_enabled: bool = True
    ai_max_concurrency_per_provider: int = 8
    ai_concurrency_timeout_s: float = 5.0
    ai_circuit_failure_threshold: int = 5
    ai_circuit_window_seconds: float = 60.0
    ai_circuit_open_seconds: float = 30.0
    # 输入 token 预检（ai/tokens.py）：超过则发送前拒绝 MODEL_INPUT_TOO_LONG；<=0 关闭
    # 场景可覆盖（scenes.SceneSpec.input_token_limit）
    ai_input_token_limit: int = 100_000
    # LLM 降级链（ai/llm/chain.py）：逗号分隔的同 provider 备用模型，空 = 关闭
    llm_fallback_models: str = ""
    # 流式请求带 stream_options.include_usage 以取回终态用量；
    # 关闭后流式调用的 token/成本审计恒为 0（部分兼容层不认该字段时可关闭）
    ai_stream_include_usage: bool = True
    # AI 思考过程（推理链）：服务端是否支持请求模型思考模式；
    # 前端开关可进一步按次关闭，此处为全局回退开关
    ai_reasoning_enabled: bool = True
    # 原生推理文本透传上限（字符）；<=0 表示不限制
    ai_reasoning_max_chars: int = 12_000
    # AI 审计僵尸回收：超窗未收尾的 running 行兜底为 failed AI_CALL_INTERRUPTED；
    # 与 async_job_stale_minutes 同口径，<=0 关闭
    ai_audit_stale_minutes: int = 30
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
    # RAG 分块与检索参数（默认值与历史行为一致；改动后须重建索引，
    # 存量分块靠 index_fingerprint 失效识别，见 scripts/reindex_all.py）
    rag_chunk_size: int = 800
    rag_chunk_overlap: int = 120
    rag_top_k: int = 5
    rag_min_score: float = 0.3
    # Judge 低分带复核的候选条数与单条截断长度
    rag_judge_top_candidates: int = 3
    rag_judge_max_excerpt_chars: int = 600
    # 向量检索后端：auto（PostgreSQL 走 pgvector、SQLite 走应用层余弦）
    # | python（强制应用层）| pgvector（强制 SQL ANN）；回滚开关
    rag_vector_backend: str = "auto"
    # ANN 过采样：HNSW + 权限过滤会损失召回，先多取再按阈值过滤并截断 top_k
    rag_ann_oversample: int = 4
    rag_ann_max_candidates: int = 200
    # HNSW 查询期 ef_search；<=0 不设置，交给 pgvector 默认值
    rag_hnsw_ef_search: int = 40
    # 增量索引：同用户、同库内（会议材料/知识库各自独立）复用同内容文件的分块，
    # 跳过解析与向量化；指纹不匹配仍走全量重建
    rag_incremental_index_enabled: bool = True
    # 索引指纹版本：分块算法变更时递增，使存量分块整体失效重建
    rag_index_fingerprint_version: int = 1
    # 联网检索（答案层后置补救）：资料无证据时先告知再联网作答；
    # 只影响答案层，不改变检索层阈值/Judge 口径；评测固定关闭
    web_search_enabled: bool = True
    web_search_provider: str = "bing"  # bing（本环境可达）| ddg
    web_search_max_results: int = 5
    web_search_timeout_s: float = 10.0
    asr_api_base: str = ""
    asr_api_key: str = ""
    asr_model: str = ""
    # 音频转写（ai/transcription/）：单次尝试超时与含重试/退避的总预算（<=0 关闭）
    asr_timeout_s: float = 120.0
    asr_call_deadline_s: float = 300.0
    # 转写降级链（ai/chain.py）：逗号分隔的同 provider 备用模型，空 = 关闭
    asr_fallback_models: str = ""
    # 音频时长预检上限（秒）：ffprobe 超限直接拒绝；ffprobe 缺失时跳过；<=0 关闭
    asr_max_audio_seconds: int = 3600
    # 实时分片是否逐片写 ai_call_logs（约 12 行/分钟，长录音行数可观）
    ai_audit_asr_chunks: bool = False
    # ASR 专用限流组：分片/重试按用户计数，与 LLM 的 20/min 分开
    rate_limit_asr_per_minute: int = 60
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

    @model_validator(mode="after")
    def _validate_rag(self) -> Settings:
        """RAG 参数互斥/取值校验：配置错误在启动期暴露，不流入检索链路。"""
        if not 0 <= self.rag_chunk_overlap < self.rag_chunk_size:
            raise ValueError("RAG_CHUNK_OVERLAP 必须满足 0 <= overlap < RAG_CHUNK_SIZE")
        if not 0 <= self.rag_min_score <= 1:
            raise ValueError("RAG_MIN_SCORE 必须在 0 到 1 之间")
        if self.rag_top_k < 1:
            raise ValueError("RAG_TOP_K 必须 >= 1")
        if self.rag_judge_top_candidates < 1:
            raise ValueError("RAG_JUDGE_TOP_CANDIDATES 必须 >= 1")
        if self.rag_judge_max_excerpt_chars < 1:
            raise ValueError("RAG_JUDGE_MAX_EXCERPT_CHARS 必须 >= 1")
        if self.rag_ann_oversample < 1:
            raise ValueError("RAG_ANN_OVERSAMPLE 必须 >= 1")
        if self.rag_ann_max_candidates < 1:
            raise ValueError("RAG_ANN_MAX_CANDIDATES 必须 >= 1")
        if self.rag_vector_backend not in {"auto", "python", "pgvector"}:
            raise ValueError("RAG_VECTOR_BACKEND 必须是 auto/python/pgvector")
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
