from fastapi import APIRouter

from app.api.v1 import ai_chat, auth, health, materials, meetings, records

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(meetings.router)
api_router.include_router(materials.router)
api_router.include_router(records.router)
api_router.include_router(ai_chat.router)
