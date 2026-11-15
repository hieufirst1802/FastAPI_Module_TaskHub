from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.v1.router import router
from app.core.config import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = create_async_engine(
            config.database_url,
            pool_pre_ping=True,
        )

        app.state.settings = config
        app.state.engine = engine
        app.state.sessions = async_sessionmaker(
            engine,
            expire_on_commit=False,
        )

        try:
            async with engine.connect() as connection:
                await connection.execute(text("SELECT 1"))

            yield
        finally:
            await engine.dispose()

    app = FastAPI(
        title="TaskHub - Bai 2 Database",
        lifespan=lifespan,
    )

    app.include_router(router)

    return app
