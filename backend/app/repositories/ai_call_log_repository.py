from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.ai_call_log import AICallLog


def insert(db: Session, log: AICallLog) -> None:
    """写入一条 AI 调用审计日志并提交。

    调用方约束：`audit_call` 只包裹纯 LLM 调用段（见 `ai_audit_service`），
    此时会话内没有未提交的业务写入，提交审计行不会连带提交业务状态。
    """
    db.add(log)
    db.commit()


def list_by_user(
    db: Session, user_id: str, *, scene: str | None = None, limit: int = 100
) -> list[AICallLog]:
    """按用户倒序取审计日志（运维/排障用；MVP 不对外暴露接口）。"""
    from sqlalchemy import select

    stmt = select(AICallLog).where(AICallLog.user_id == user_id)
    if scene:
        stmt = stmt.where(AICallLog.scene == scene)
    stmt = stmt.order_by(AICallLog.created_at.desc()).limit(limit)
    return list(db.execute(stmt).scalars())
