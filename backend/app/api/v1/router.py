from fastapi import APIRouter

from app.api.v1 import auth, health, materials, meetings, preparations

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(meetings.router)
api_router.include_router(materials.router)
api_router.include_router(preparations.router)
