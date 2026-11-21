from fastapi import APIRouter
from sqlalchemy import text

from app.core.database import Session

router = APIRouter()


@router.get("/health")
async def health(session: Session) -> dict[str, str]:
    await session.execute(text("SELECT 1"))
    return {"status": "ok"}
