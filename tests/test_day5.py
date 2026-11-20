import logging

from fastapi import HTTPException
from fastapi.testclient import TestClient
from starlette.responses import StreamingResponse

from app.main import create_app

REQUEST_LOGGER = "app.middleware.request_logging"
ERROR_LOGGER = "app.core.exception_handlers"


def test_request_logging_adds_process_time_and_logs_at_info(public_client, caplog):
    response = public_client.get("/health?private=value")

    assert response.status_code == 200
    assert float(response.headers["X-Process-Time"]) >= 0
    records = [record for record in caplog.records if record.name == REQUEST_LOGGER]
    assert len(records) == 1
    assert records[0].levelno == logging.INFO
    assert records[0].getMessage().startswith("GET /health 200 ")
    assert "private=value" not in records[0].getMessage()


def test_log_level_from_settings_suppresses_info(settings, caplog):
    settings = settings.model_copy(update={"log_level": "WARNING"})
    with TestClient(create_app(settings)) as client:
        assert client.get("/health").status_code == 200

    assert not any(record.name == REQUEST_LOGGER for record in caplog.records)


def test_validation_error_excludes_password_and_raw_context(public_client):
    password = "secret7"
    response = public_client.post(
        "/api/v1/auth/register", json={"username": "valid_user", "password": password}
    )

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert error["message"] == "Request validation failed"
    assert len(error["details"]) == 1
    detail = error["details"][0]
    assert set(detail) == {"loc", "msg", "type"}
    assert detail["loc"] == ["body", "password"]
    assert password not in response.text


def test_app_exception_codes_and_auth_header(public_client, registered_user, client, account):
    duplicate = public_client.post("/api/v1/auth/register", json=account)
    assert duplicate.status_code == 409
    assert duplicate.json() == {
        "error": {
            "code": "username_already_exists",
            "message": "Username already registered",
        }
    }

    login = public_client.post(
        "/api/v1/auth/login", json={**account, "password": "incorrect-password"}
    )
    assert login.status_code == 401
    assert login.headers["WWW-Authenticate"] == "Bearer"
    assert login.json()["error"]["code"] == "unauthorized"

    unauthenticated = public_client.get("/api/v1/tasks", headers={"Authorization": ""})
    assert unauthenticated.status_code == 401
    assert unauthenticated.headers["WWW-Authenticate"] == "Bearer"
    assert unauthenticated.json()["error"]["code"] == "unauthorized"

    forbidden = client.get("/api/v1/users")
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "forbidden"


def test_http_exception_preserves_structured_detail_and_headers(settings):
    app = create_app(settings)
    detail = {"issues": [{"field": "status"}]}

    @app.get("/test-structured-error")
    async def trigger_error():
        raise HTTPException(status_code=400, detail=detail, headers={"X-Test": "preserved"})

    with TestClient(app) as client:
        response = client.get("/test-structured-error")

    assert response.status_code == 400
    assert response.json() == {"error": {"code": "http_error", "message": detail}}
    assert response.headers["X-Test"] == "preserved"


def test_unhandled_error_returns_safe_response_and_logs_once(settings, caplog):
    app = create_app(settings)

    @app.get("/test-unhandled-error")
    async def trigger_error():
        raise RuntimeError("Sensitive internal detail")

    with TestClient(app) as client:
        response = client.get("/test-unhandled-error")

    assert response.status_code == 500
    assert float(response.headers["X-Process-Time"]) >= 0
    assert response.json() == {
        "error": {
            "code": "internal_server_error",
            "message": "An unexpected error occurred",
        }
    }
    assert "Sensitive internal detail" not in response.text

    records = [record for record in caplog.records if record.exc_info]
    assert len(records) == 1
    assert records[0].name == ERROR_LOGGER
    assert records[0].exc_info[0] is RuntimeError

    access_logs = [record for record in caplog.records if record.name == REQUEST_LOGGER]
    assert len(access_logs) == 1
    assert access_logs[0].getMessage().startswith("GET /test-unhandled-error 500 ")


def test_request_logging_preserves_streaming_response(settings):
    app = create_app(settings)

    async def chunks():
        yield b"first"
        yield b"second"

    @app.get("/test-stream")
    async def stream():
        return StreamingResponse(chunks())

    with TestClient(app) as client:
        response = client.get("/test-stream")

    assert response.status_code == 200
    assert response.content == b"firstsecond"
    assert float(response.headers["X-Process-Time"]) >= 0
