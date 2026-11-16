from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, Numeric, String, func
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.user import utc_now

_meta_type = JSON().with_variant(postgresql.JSONB(), "postgresql")


class AICallLog(Base):
    """AI 调用审计日志（`database.md 3.18`）：只存元数据与用量，不存提示词/原文。

    **预创建运行态**（`ai-design.md 3.11`）：调用开始即落一行 `status=running`，
    收尾时更新为 `success`/`failed`/`cancelled` 并写 `finished_at`——进程崩溃
    留下的 `running` 行由僵尸回收兜底为 `failed AI_CALL_INTERRUPTED`。
    同步/流式/降级切换后实际发出的请求各一行；写入失败只记日志、不影响
    业务调用（审计是旁路）。
    """

    __tablename__ = "ai_call_logs"
    __table_args__ = (
        Index("ix_ai_call_logs_user_created", "user_id", "created_at"),
        Index("ix_ai_call_logs_scene_created", "scene", "created_at"),
        Index("ix_ai_call_logs_job_created", "job_id", "created_at"),
        Index("ix_ai_call_logs_user_status", "user_id", "status", "created_at"),
    )

    log_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(40), ForeignKey("users.user_id"), nullable=False
    )
    # 关联 async_jobs.job_id（后台任务内产生的调用）；同步调用为空。
    # 不建 FK：审计 append-only，任务清理不应连坐日志
    job_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    # 场景名（ai/scenes.py 注册表键）与 BYOK 用途；用途可为空（如 RAG Judge）
    scene: Mapped[str] = mapped_column(String(40), nullable=False)
    purpose: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # 实际发出请求的模型（降级链切换后为候选模型）与 provider host
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    provider: Mapped[str] = mapped_column(String(200), nullable=False)
    # 流式/同步；成功与失败都落库
    transport: Mapped[str] = mapped_column(
        String(10), nullable=False, default="sync", server_default="sync"
    )
    # running（预创建）→ success | failed | cancelled（终态）
    status: Mapped[str] = mapped_column(
        String(10), nullable=False, default="success", server_default="success"
    )
    error_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 估算成本（USD，pricing.py 按模型单价 × token 数算得出；未知单价为 NULL）
    cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
    latency_ms: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    # 降级链切换时记录起点模型（未切换为 NULL）
    fallback_from: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # 降级来源标签：none / global（本期）；user / scene / cross_provider 为后续预留
    fallback_scope: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # 纯标签扩展（如 {"chain_len": "3"}）；禁止提示词、用户原文与模型输出
    meta: Mapped[dict] = mapped_column(_meta_type, nullable=False, default=dict)
    # 预创建/受理时间（= 调用开始）
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, server_default=func.now()
    )
    # 进入终态时间；running 行为 NULL
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
