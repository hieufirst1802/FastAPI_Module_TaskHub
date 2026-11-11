import logging
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from starlette.exceptions import HTTPException
from starlette.responses import Response

from app.api import router
from app.cache import Cache
from app.config import Settings, get_settings
from app.security import passwords

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = create_async_engine(config.database_url, pool_pre_ping=True)
        client: Redis | None = (
            Redis.from_url(config.redis_url, decode_responses=True) if config.redis_url else None
        )
        app.state.settings = config
        app.state.sessions = async_sessionmaker(engine, expire_on_commit=False)
        app.state.cache = Cache(client, config.cache_seconds)
        app.state.dummy_hash = passwords.hash("dummy-password-for-timing")
        try:
            async with engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
            if config.environment == "production" and client:
                await client.execute_command("PING")  # type: ignore[no-untyped-call]
            yield
        finally:
            if client:
                await client.aclose()
            await engine.dispose()

    app = FastAPI(
        title="Task Manager Practice",
        version="1.0.0",
        lifespan=lifespan,
        description="Layered FastAPI sample: JWT, RBAC, ownership, async CRUD, Redis.",
    )

    @app.middleware("http")
    async def request_log(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request.state.request_id = uuid.uuid4().hex
        start = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["X-Process-Time"] = str(round(time.perf_counter() - start, 6))
        logger.info(
            "request=%s method=%s path=%s status=%s",
            request.state.request_id,
            request.method,
            request.url.path,
            response.status_code,
        )
        return response

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            headers=exc.headers,
            content={"error": {"message": exc.detail}, "request_id": request.state.request_id},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "message": "Validation failed",
                    "details": [{"loc": list(e["loc"]), "msg": e["msg"]} for e in exc.errors()],
                },
                "request_id": request.state.request_id,
            },
        )

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled request error", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content={
                "error": {"message": "Internal server error"},
                "request_id": getattr(request.state, "request_id", None),
            },
        )

    @app.get("/health", tags=["Operations"])
    async def health(request: Request) -> dict[str, str]:
        async with request.app.state.sessions() as session:
            await session.execute(text("SELECT 1"))
        return {"status": "ok"}

    app.include_router(router)
    return app
