from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.v1.router import router
from app.core.exceptions import TaskNotFoundError
from app.repositories.task import TaskRepository


def create_app() -> FastAPI:

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.repository = TaskRepository()
        yield

    app = FastAPI(
        title="TaskHub - Day 1 Core Setup",
        description="FastAPI CRUD with layered architecture",
        version="1.0.0",
        lifespan=lifespan,
    )

    @app.exception_handler(TaskNotFoundError)
    async def task_not_found_handler(
        request: Request,
        exc: TaskNotFoundError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={"detail": "Task not found"},
        )

    app.include_router(router)

    return app