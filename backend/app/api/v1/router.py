from fastapi import APIRouter

from app.api.v1 import (
    action_items,
    ai_chat,
    auth,
    health,
    issues,
    knowledge,
    materials,
    meetings,
    minutes,
    preparations,
    records,
    settings,
    tasks,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(meetings.router)
api_router.include_router(materials.router)
api_router.include_router(preparations.router)
api_router.include_router(records.router)
api_router.include_router(ai_chat.router)
api_router.include_router(minutes.router)
api_router.include_router(action_items.router)
api_router.include_router(tasks.router)
api_router.include_router(issues.router)
api_router.include_router(knowledge.router)
api_router.include_router(settings.router)
