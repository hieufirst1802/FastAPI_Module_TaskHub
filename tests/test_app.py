import asyncio
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import Settings
from app.main import create_app
from app.models import Base

SECRET = "test-secret-" * 5


@pytest.fixture
def client(tmp_path):
    url = f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"

    async def setup():
        engine = create_async_engine(url)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        await engine.dispose()

    asyncio.run(setup())
    with TestClient(create_app(Settings(database_url=url, jwt_secret=SECRET))) as client:
        yield client


def account(client, username):
    response = client.post(
        "/api/auth/register", json={"username": username, "password": "Password123!"}
    )
    assert response.status_code == 201
    assert "password_hash" not in response.json()
    response = client.post(
        "/api/auth/token", data={"username": username, "password": "Password123!"}
    )
    assert response.status_code == 200
    return {"Authorization": "Bearer " + response.json()["access_token"]}


def test_crud_ownership_and_pagination(client):
    alice = account(client, "alice")
    bob = account(client, "bobby")
    response = client.post("/api/tasks", headers=alice, json={"title": "Learn FastAPI"})
    assert response.status_code == 201
    identifier = response.json()["id"]
    path = f"/api/tasks/{identifier}"
    assert client.get(path, headers=alice).json()["title"] == "Learn FastAPI"
    for method in ("get", "patch", "delete"):
        kwargs = {"json": {"title": "stolen"}} if method == "patch" else {}
        assert getattr(client, method)(path, headers=bob, **kwargs).status_code == 404
    assert client.get("/api/tasks", headers=bob).json()["total"] == 0
    page = client.get("/api/tasks?limit=1", headers=alice).json()
    assert page["total"] == 1 and len(page["items"]) == 1
    assert client.patch(path, headers=alice, json={"completed": True}).json()["completed"]
    assert client.get(path, headers=alice).json()["completed"]
    assert client.delete(path, headers=alice).status_code == 204
    assert client.get(path, headers=alice).status_code == 404


def test_auth_and_validation(client):
    headers = account(client, "alice")
    assert client.get("/api/tasks").status_code == 401
    assert client.get("/api/admin/users", headers=headers).status_code == 403
    assert client.get("/api/users/me", headers=headers).json()["role"] == "member"
    assert (
        client.post(
            "/api/auth/register", json={"username": "alice", "password": "Password123!"}
        ).status_code
        == 409
    )
    assert (
        client.post("/api/auth/token", data={"username": "alice", "password": "wrong"}).status_code
        == 401
    )
    assert client.post("/api/tasks", headers=headers, json={"title": "  "}).status_code == 422
    assert client.get("/api/tasks?limit=101", headers=headers).status_code == 422
    assert client.patch("/api/tasks/1", headers=headers, json={"title": None}).status_code == 422
    assert (
        client.post("/api/tasks", headers=headers, json={"title": "ok", "owner_id": 2}).status_code
        == 422
    )
    expired = jwt.encode(
        {
            "sub": "1",
            "iat": datetime.now(UTC) - timedelta(hours=2),
            "exp": datetime.now(UTC) - timedelta(hours=1),
        },
        SECRET,
        algorithm="HS256",
    )
    assert (
        client.get("/api/tasks", headers={"Authorization": "Bearer " + expired}).status_code == 401
    )
    assert client.get("/health").status_code == 200
    assert client.get("/openapi.json").status_code == 200


def test_settings_fail_fast():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Settings(jwt_secret="short")
    with pytest.raises(ValidationError):
        Settings(jwt_secret=SECRET, environment="production", redis_url=None)


def test_admin_can_manage_other_users_tasks(client):
    alice = account(client, "alice")
    task = client.post("/api/tasks", headers=alice, json={"title": "Member task"}).json()

    # Provision a real admin via the same database used by this app.
    async def provision():
        from app.repositories import UserRepository
        from app.security import passwords

        async with client.app.state.sessions() as session:
            await UserRepository(session).create(
                username="administrator", password_hash=passwords.hash("Password123!"), role="admin"
            )

    client.portal.call(provision)
    token = client.post(
        "/api/auth/token", data={"username": "administrator", "password": "Password123!"}
    ).json()["access_token"]
    admin = {"Authorization": "Bearer " + token}
    assert len(client.get("/api/admin/users", headers=admin).json()) == 2
    assert client.get("/api/tasks", headers=admin).json()["total"] == 1
    assert (
        client.patch(
            f"/api/tasks/{task['id']}", headers=admin, json={"completed": True}
        ).status_code
        == 200
    )
    assert client.delete(f"/api/tasks/{task['id']}", headers=admin).status_code == 204
