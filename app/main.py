from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.api.v1.endpoints.health import router as health_router
from app.api.v1.router import router
from app.core.config import Settings, get_settings
from app.core.database import create_engine
from app.core.exceptions import AppException, handle_app_exception


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = create_engine(config.database_url)

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
        title="TaskHub - Bai 3 Authentication",
        lifespan=lifespan,
    )

    app.add_exception_handler(AppException, handle_app_exception)
    app.include_router(health_router)
    app.include_router(router)

    return app
