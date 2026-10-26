from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.user_memory import UserMemory


def get_by_user(db: Session, user_id: str) -> UserMemory | None:
    return db.get(UserMemory, user_id)


def upsert(
    db: Session,
    *,
    user_id: str,
    role: str | None,
    work_scenarios: str | None,
    communication_style: str | None,
    preferred_minutes_template: str | None,
) -> UserMemory:
    memory = db.get(UserMemory, user_id)
    if memory is None:
        memory = UserMemory(user_id=user_id)
        db.add(memory)
    memory.role = role
    memory.work_scenarios = work_scenarios
    memory.communication_style = communication_style
    memory.preferred_minutes_template = preferred_minutes_template
    db.commit()
    db.refresh(memory)
    return memory


def delete(db: Session, memory: UserMemory) -> None:
    db.delete(memory)
    db.commit()
