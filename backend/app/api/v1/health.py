from fastapi import APIRouter, HTTPException, status

from app.db.session import check_database

router = APIRouter(tags=["health"])


@router.get("/health/db")
def health_db() -> dict[str, str]:
    if not check_database():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="数据库不可用",
        )
    return {"status": "ok", "database": "up"}
