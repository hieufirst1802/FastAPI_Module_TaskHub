from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.v1.router import router
from app.core.constants import APP_TITLE
from app.core.exceptions import AppException
from app.repositories.task import TaskRepository


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.repository = TaskRepository()
        yield

    app = FastAPI(
        title=APP_TITLE,
        description="FastAPI CRUD with layered architecture",
        version="1.0.0",
        lifespan=lifespan,
    )

    @app.exception_handler(AppException)
    async def app_exception_handler(
        request: Request,
        exc: AppException,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message},
        )

    app.include_router(router)

    return app
