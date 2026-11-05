from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.models.user_memory import UserMemory
from app.repositories import memory_repository
from app.schemas.memory import MemoryRead, MemoryWrite, is_builtin_template_value


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    return text or None


# 注入 prompt 的用户画像总长上限（字符），防止记忆内容挤占会议业务资料上下文
_MAX_MEMORY_CONTEXT_CHARS = 500


def get_memory(db: Session, user_id: str) -> UserMemory | None:
    return memory_repository.get_by_user(db, user_id)


def get_memory_read(db: Session, user_id: str) -> MemoryRead:
    memory = get_memory(db, user_id)
    if memory is None:
        return MemoryRead(
            role="",
            work_scenarios="",
            communication_style="",
            preferred_minutes_template=None,
            updated_at=None,
        )
    return MemoryRead(
        role=memory.role or "",
        work_scenarios=memory.work_scenarios or "",
        communication_style=memory.communication_style or "",
        preferred_minutes_template=memory.preferred_minutes_template,
        updated_at=memory.updated_at,
    )


def save_memory(db: Session, user_id: str, payload: MemoryWrite) -> UserMemory:
    preferred = _clean(payload.preferred_minutes_template)
    if preferred is not None and not is_builtin_template_value(preferred):
        # 非内置枚举值时必须是模板清单中真实存在的模板 id
        from app.services import meeting_template_service

        try:
            meeting_template_service.resolve_template_content(db, user_id, preferred)
        except AppError:
            raise AppError(
                "VALIDATION_ERROR", "默认纪要模板不存在", http_status=422
            ) from None
    return memory_repository.upsert(
        db,
        user_id=user_id,
        role=_clean(payload.role),
        work_scenarios=_clean(payload.work_scenarios),
        communication_style=_clean(payload.communication_style),
        preferred_minutes_template=preferred,
    )


def clear_memory(db: Session, user_id: str) -> None:
    memory = get_memory(db, user_id)
    if memory is not None:
        memory_repository.delete(db, memory)


def preferred_minutes_template(db: Session, user_id: str) -> str | None:
    memory = get_memory(db, user_id)
    return memory.preferred_minutes_template if memory else None


def _clip_context(parts: list[str], limit: int = _MAX_MEMORY_CONTEXT_CHARS) -> str:
    """按字段顺序拼接并限制总长：超限时当前字段按剩余空间截断并加省略号后停止。

    字段按整行语义截断（不保留半行），保证画像不挤占会议业务资料的上下文窗口。
    """
    out: list[str] = []
    used = 0
    for part in parts:
        separator = 1 if out else 0  # 换行符计入总长
        remaining = limit - used - separator
        if remaining <= 0:
            break
        if len(part) <= remaining:
            line = part
        else:
            line = part[: max(remaining - 1, 0)] + "…"
        out.append(line)
        used += separator + len(line)
        if len(line) < len(part):
            break  # 已截断，后续字段整体丢弃
    return "\n".join(out)


def memory_context_for(db: Session, user_id: str, purpose: str) -> str:
    memory = get_memory(db, user_id)
    if memory is None:
        return ""

    parts: list[str] = []
    if purpose == "preparation":
        if memory.role:
            parts.append(f"用户角色：{memory.role}")
        if memory.work_scenarios:
            parts.append(f"工作场景：{memory.work_scenarios}")
        if memory.communication_style:
            parts.append(f"表达偏好：{memory.communication_style}")
    elif purpose in {"minutes", "chat"} and memory.communication_style:
        parts.append(f"表达偏好：{memory.communication_style}")
    return _clip_context(parts)
