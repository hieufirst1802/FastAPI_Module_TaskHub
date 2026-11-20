import sqlite3

from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.core.config import Settings
from app.main import create_app


def test_request_logging_middleware_adds_process_time_header(
    settings: Settings,
) -> None:

    with TestClient(create_app(settings)) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert "X-Process-Time" in response.headers
    assert float(response.headers["X-Process-Time"]) >= 0


def test_unexpected_integrity_error_is_logged_as_server_error(settings, caplog):
    app = create_app(settings)

    @app.get("/test-unexpected-integrity")
    async def unexpected_integrity_error() -> None:
        raise IntegrityError(None, None, sqlite3.IntegrityError("NOT NULL constraint failed"))

    with TestClient(app) as client:
        response = client.get("/test-unexpected-integrity")

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_server_error"
    assert "NOT NULL" not in response.text
    errors = [record for record in caplog.records if record.name == "app.core.exception_handlers"]
    assert len(errors) == 1
    assert errors[0].exc_info[0] is IntegrityError


def test_validation_exception_handler_returns_standard_error(
    settings: Settings,
) -> None:

    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/v1/auth/register",
            json={"username": "ab", "password": "123"},
        )

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    assert body["error"]["message"] == "Request validation failed"
    assert body["error"]["details"]


def test_custom_exception_handler_returns_conflict(
    settings: Settings,
) -> None:

    with TestClient(create_app(settings)) as client:
        payload = {
            "username": "duplicate_user",
            "password": "StrongPassword123!",
        }
        first = client.post("/api/v1/auth/register", json=payload)
        second = client.post("/api/v1/auth/register", json=payload)

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json() == {
        "error": {
            "code": "username_already_exists",
            "message": "Username already registered",
        }
    }


def test_unhandled_exception_handler_returns_safe_response(
    settings: Settings,
) -> None:
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
