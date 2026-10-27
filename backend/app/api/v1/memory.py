from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.schemas.common import Envelope
from app.schemas.memory import MemoryDeleteResult, MemoryRead, MemoryWrite
from app.services import memory_service

router = APIRouter(tags=["memory"])


@router.get("/me/memory", response_model=Envelope[MemoryRead])
def get_memory(db: DbSession, current_user: CurrentUser) -> Envelope[MemoryRead]:
    return Envelope(data=memory_service.get_memory_read(db, current_user.user_id))


@router.put("/me/memory", response_model=Envelope[MemoryRead])
def put_memory(
    payload: MemoryWrite, db: DbSession, current_user: CurrentUser
) -> Envelope[MemoryRead]:
    memory_service.save_memory(db, current_user.user_id, payload)
    return Envelope(data=memory_service.get_memory_read(db, current_user.user_id))


@router.delete("/me/memory", response_model=Envelope[MemoryDeleteResult])
def delete_memory(
    db: DbSession, current_user: CurrentUser
) -> Envelope[MemoryDeleteResult]:
    memory_service.clear_memory(db, current_user.user_id)
    return Envelope(data=MemoryDeleteResult())
