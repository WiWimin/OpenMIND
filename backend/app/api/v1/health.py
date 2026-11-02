from fastapi import APIRouter, status

from app.core.exceptions import AppError
from app.db.session import check_database

router = APIRouter(tags=["health"])


@router.get("/health/db")
def health_db() -> dict[str, str]:
    if not check_database():
        raise AppError(
            "INTERNAL_ERROR",
            "数据库不可用",
            http_status=status.HTTP_503_SERVICE_UNAVAILABLE,
            retryable=True,
        )
    return {"status": "ok", "database": "up"}
