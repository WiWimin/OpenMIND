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
    return "\n".join(parts)
