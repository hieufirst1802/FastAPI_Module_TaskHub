import asyncio
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import Settings
from app.main import create_app
from app.models import Base


def prepare_database(settings: Settings) -> None:
    async def create_schema() -> None:
        engine = create_async_engine(settings.database_url)
        try:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
        finally:
            await engine.dispose()

    asyncio.run(create_schema())


def make_settings(tmp_path: Path) -> Settings:
    return Settings(
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'day5.db').as_posix()}"
    )


def test_request_logging_middleware_adds_process_time_header(
    tmp_path: Path,
) -> None:
    settings = make_settings(tmp_path)

    with TestClient(create_app(settings)) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert "X-Process-Time" in response.headers
    assert float(response.headers["X-Process-Time"]) >= 0


def test_validation_exception_handler_returns_standard_error(
    tmp_path: Path,
) -> None:
    settings = make_settings(tmp_path)

    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/auth/register",
            json={"username": "ab", "password": "123"},
        )

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    assert body["error"]["message"] == "Request validation failed"
    assert body["error"]["details"]


def test_custom_exception_handler_returns_conflict(
    tmp_path: Path,
) -> None:
    settings = make_settings(tmp_path)
    prepare_database(settings)

    with TestClient(create_app(settings)) as client:
        payload = {
            "username": "duplicate_user",
            "password": "StrongPassword123!",
        }
        first = client.post("/api/auth/register", json=payload)
        second = client.post("/api/auth/register", json=payload)

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json() == {
        "error": {
            "code": "username_already_exists",
            "message": "Username already registered",
        }
    }


def test_unhandled_exception_handler_returns_safe_response(
    tmp_path: Path,
) -> None:
    settings = make_settings(tmp_path)
    app = create_app(settings)

    async def trigger_error() -> None:
        raise RuntimeError("Sensitive internal detail")

    app.add_api_route(
        "/test-unhandled-error",
        trigger_error,
        methods=["GET"],
    )

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/test-unhandled-error")

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "internal_server_error",
            "message": "An unexpected error occurred",
        }
    }
