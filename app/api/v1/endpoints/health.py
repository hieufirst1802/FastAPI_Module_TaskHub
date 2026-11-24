from fastapi import APIRouter
from sqlalchemy import text

from app.core.database import Session

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    summary="Check database readiness",
    description="Execute a database query and return status ok if it succeeds.",
)
async def health(session: Session) -> dict[str, str]:
    await session.execute(text("SELECT 1"))
    return {"status": "ok"}
