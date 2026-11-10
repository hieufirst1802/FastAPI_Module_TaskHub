from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api import router
from app.config import Settings, get_settings
from app.security import passwords


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = create_async_engine(config.database_url, pool_pre_ping=True)
        app.state.settings = config
        app.state.dummy_hash = passwords.hash("dummy-password-for-timing")
        app.state.sessions = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
            yield
        finally:
            await engine.dispose()

    app = FastAPI(title="TaskHub - Bai 3 Authentication and RBAC", lifespan=lifespan)

    @app.get("/health")
    async def health(request: Request) -> dict[str, str]:
        async with request.app.state.sessions() as session:
            await session.execute(text("SELECT 1"))
        return {"status": "ok"}

    app.include_router(router)
    return app
