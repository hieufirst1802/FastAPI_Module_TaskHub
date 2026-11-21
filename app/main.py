import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.v1.router import router
from app.core.cache import TaskCache
from app.core.config import Settings, get_settings
from app.core.exception_handlers import register_exception_handlers
from app.middleware.request_logging import RequestLoggingMiddleware
from app.middleware.unhandled_errors import UnhandledErrorMiddleware


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        logging.basicConfig(level=config.log_level)
        logging.getLogger("app").setLevel(config.log_level)
        engine = create_async_engine(
            config.database_url,
            pool_pre_ping=True,
        )

        if engine.dialect.name == "sqlite":

            @event.listens_for(engine.sync_engine, "connect")
            def enable_foreign_keys(connection: Any, record: Any) -> None:
                cursor = connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()

        app.state.settings = config
        app.state.engine = engine
        app.state.sessions = async_sessionmaker(
            engine,
            expire_on_commit=False,
        )

        cache = TaskCache.from_settings(config)
        app.state.task_cache = cache

        try:
            async with engine.connect() as connection:
                await connection.execute(text("SELECT 1"))

            yield
        finally:
            await cache.close()
            await engine.dispose()

    app = FastAPI(
        title="TaskHub - FastAPI Practice",
        lifespan=lifespan,
    )

    app.add_middleware(UnhandledErrorMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
    register_exception_handlers(app)
    app.include_router(router)

    return app
