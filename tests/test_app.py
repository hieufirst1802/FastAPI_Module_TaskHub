import asyncio
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import text
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


def update_user_role(
    settings: Settings,
    username: str,
    role: str,
) -> None:
    async def update_role() -> None:
        engine = create_async_engine(settings.database_url)

        try:
            async with engine.begin() as connection:
                await connection.execute(
                    text("UPDATE users SET role = :role WHERE username = :username"),
                    {"role": role, "username": username},
                )
        finally:
            await engine.dispose()

    asyncio.run(update_role())


def test_crud_validation_and_pagination(tmp_path: Path) -> None:
    settings = Settings(database_url=f"sqlite+aiosqlite:///{(tmp_path / 'test.db').as_posix()}")
    prepare_database(settings)

    with TestClient(create_app(settings)) as client:
        assert client.get("/health").json() == {"status": "ok"}

        # Register and login
        registered = client.post(
            "/api/auth/register",
            json={
                "username": "cruduser",
                "password": "CrudPassword123!",
            },
        )
        assert registered.status_code == 201

        login = client.post(
            "/api/auth/login",
            json={
                "username": "cruduser",
                "password": "CrudPassword123!",
            },
        )
        assert login.status_code == 200

        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        # Validation
        invalid = client.post(
            "/api/tasks",
            json={"title": " "},
            headers=headers,
        )
        assert invalid.status_code == 422

        # Create first task
        response = client.post(
            "/api/tasks",
            json={"title": "Learn routing"},
            headers=headers,
        )
        assert response.status_code == 201

        task = response.json()
        identifier = task["id"]

        assert task["title"] == "Learn routing"
        assert task["description"] == ""
        assert task["completed"] is False
        assert task["owner_id"] == registered.json()["id"]

        # Create second task
        second = client.post(
            "/api/tasks",
            json={
                "title": "Learn database",
                "description": "Practice SQLAlchemy",
            },
            headers=headers,
        )
        assert second.status_code == 201

        # Pagination
        page_response = client.get("/api/tasks", headers=headers)
        assert page_response.status_code == 200

        page = page_response.json()
        assert len(page["items"]) == 2
        assert page["total"] == 2
        assert page["offset"] == 0
        assert page["limit"] == 20

        next_page_response = client.get(
            "/api/tasks?offset=1&limit=1",
            headers=headers,
        )
        assert next_page_response.status_code == 200

        next_page = next_page_response.json()
        assert len(next_page["items"]) == 1
        assert next_page["total"] == 2
        assert next_page["offset"] == 1
        assert next_page["limit"] == 1

        # Read
        detail = client.get(
            f"/api/tasks/{identifier}",
            headers=headers,
        )
        assert detail.status_code == 200
        assert detail.json()["title"] == "Learn routing"

        # Update
        updated = client.patch(
            f"/api/tasks/{identifier}",
            json={"completed": True},
            headers=headers,
        )
        assert updated.status_code == 200
        assert updated.json()["completed"] is True

        null_update = client.patch(
            f"/api/tasks/{identifier}",
            json={"title": None},
            headers=headers,
        )
        assert null_update.status_code == 422

        # Delete
        deleted = client.delete(
            f"/api/tasks/{identifier}",
            headers=headers,
        )
        assert deleted.status_code == 204

        missing = client.get(
            f"/api/tasks/{identifier}",
            headers=headers,
        )
        assert missing.status_code == 404

        assert client.get("/openapi.json").status_code == 200


def test_database_persistence_across_app_restart(tmp_path: Path) -> None:
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'persistent.db').as_posix()}"
    )
    prepare_database(settings)

    with TestClient(create_app(settings)) as client:
        registered = client.post(
            "/api/auth/register",
            json={
                "username": "persistentuser",
                "password": "PersistentPassword123!",
            },
        )
        assert registered.status_code == 201

        login = client.post(
            "/api/auth/login",
            json={
                "username": "persistentuser",
                "password": "PersistentPassword123!",
            },
        )
        assert login.status_code == 200

        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        response = client.post(
            "/api/tasks",
            json={"title": "Persistent task"},
            headers=headers,
        )
        assert response.status_code == 201
        identifier = response.json()["id"]

    # Restart application
    with TestClient(create_app(settings)) as client:
        login = client.post(
            "/api/auth/login",
            json={
                "username": "persistentuser",
                "password": "PersistentPassword123!",
            },
        )
        assert login.status_code == 200

        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        response = client.get(
            f"/api/tasks/{identifier}",
            headers=headers,
        )

        assert response.status_code == 200
        assert response.json()["title"] == "Persistent task"


def test_authentication_flow(tmp_path: Path) -> None:
    settings = Settings(database_url=f"sqlite+aiosqlite:///{(tmp_path / 'auth.db').as_posix()}")
    prepare_database(settings)

    with TestClient(create_app(settings)) as client:
        # 1. Register successfully
        registered = client.post(
            "/api/auth/register",
            json={
                "username": "authuser",
                "password": "TestPassword123!",
            },
        )

        assert registered.status_code == 201
        user = registered.json()

        assert user["id"] > 0
        assert user["username"] == "authuser"
        assert user["role"] == "member"
        assert "password_hash" not in user

        # 2. Reject duplicate username
        duplicate = client.post(
            "/api/auth/register",
            json={
                "username": "authuser",
                "password": "AnotherPassword123!",
            },
        )

        assert duplicate.status_code == 409

        # 3. Reject invalid registration data
        invalid = client.post(
            "/api/auth/register",
            json={
                "username": "ab",
                "password": "123",
            },
        )

        assert invalid.status_code == 422

        # 4. Reject incorrect password
        wrong_login = client.post(
            "/api/auth/login",
            json={
                "username": "authuser",
                "password": "WrongPassword123!",
            },
        )

        assert wrong_login.status_code == 401

        # 5. Login successfully
        login = client.post(
            "/api/auth/login",
            json={
                "username": "authuser",
                "password": "TestPassword123!",
            },
        )

        assert login.status_code == 200

        token_data = login.json()
        assert token_data["token_type"] == "bearer"
        assert token_data["access_token"]

        headers = {"Authorization": f"Bearer {token_data['access_token']}"}

        # 6. Access current user with valid token
        me = client.get("/api/auth/me", headers=headers)

        assert me.status_code == 200
        assert me.json()["id"] == user["id"]
        assert me.json()["username"] == "authuser"

        # 7. Reject missing token
        missing_token = client.get("/api/auth/me")
        assert missing_token.status_code == 401

        # 8. Reject invalid token
        invalid_token = client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer invalid-token"},
        )

        assert invalid_token.status_code == 401


def test_user_rbac(tmp_path: Path) -> None:
    settings = Settings(database_url=f"sqlite+aiosqlite:///{(tmp_path / 'rbac.db').as_posix()}")
    prepare_database(settings)

    with TestClient(create_app(settings)) as client:
        # 1. Anonymous user must be rejected
        anonymous = client.get("/api/users")
        assert anonymous.status_code == 401

        # 2. Register a member
        member = client.post(
            "/api/auth/register",
            json={
                "username": "memberuser",
                "password": "MemberPassword123!",
            },
        )
        assert member.status_code == 201

        # 3. Login as member
        member_login = client.post(
            "/api/auth/login",
            json={
                "username": "memberuser",
                "password": "MemberPassword123!",
            },
        )
        assert member_login.status_code == 200

        member_token = member_login.json()["access_token"]
        member_headers = {"Authorization": f"Bearer {member_token}"}

        # 4. Member must be forbidden
        forbidden = client.get(
            "/api/users",
            headers=member_headers,
        )
        assert forbidden.status_code == 403

        # 5. Register another user, then promote it to admin
        admin = client.post(
            "/api/auth/register",
            json={
                "username": "adminuser",
                "password": "AdminPassword123!",
            },
        )
        assert admin.status_code == 201

        update_user_role(settings, "adminuser", "admin")

        # 6. Login as admin
        admin_login = client.post(
            "/api/auth/login",
            json={
                "username": "adminuser",
                "password": "AdminPassword123!",
            },
        )
        assert admin_login.status_code == 200

        admin_token = admin_login.json()["access_token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        # 7. Admin can access users
        response = client.get(
            "/api/users",
            headers=admin_headers,
        )
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2
        assert data["offset"] == 0
        assert data["limit"] == 20

        # 8. Password hashes must never be exposed
        for user in data["items"]:
            assert "password_hash" not in user


def test_task_ownership_and_admin_access(tmp_path: Path) -> None:
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'ownership.db').as_posix()}"
    )
    prepare_database(settings)

    with TestClient(create_app(settings)) as client:
        # 1. Anonymous user cannot access tasks
        anonymous = client.get("/api/tasks")
        assert anonymous.status_code == 401

        # 2. Register two members
        for username in ("member_a", "member_b"):
            response = client.post(
                "/api/auth/register",
                json={
                    "username": username,
                    "password": "MemberPassword123!",
                },
            )
            assert response.status_code == 201

        # 3. Login both members
        def login(username: str) -> dict[str, str]:
            response = client.post(
                "/api/auth/login",
                json={
                    "username": username,
                    "password": "MemberPassword123!",
                },
            )
            assert response.status_code == 200

            return {"Authorization": (f"Bearer {response.json()['access_token']}")}

        headers_a = login("member_a")
        headers_b = login("member_b")

        # 4. Member A creates a task
        created = client.post(
            "/api/tasks",
            json={"title": "Task owned by A"},
            headers=headers_a,
        )
        assert created.status_code == 201

        task_id = created.json()["id"]

        # 5. Member B creates another task
        created_b = client.post(
            "/api/tasks",
            json={"title": "Task owned by B"},
            headers=headers_b,
        )
        assert created_b.status_code == 201

        # 6. Member B can only see their own task
        page_b = client.get("/api/tasks", headers=headers_b)
        assert page_b.status_code == 200
        assert page_b.json()["total"] == 1
        assert page_b.json()["items"][0]["title"] == "Task owned by B"

        # 7. Member B cannot access member A's task
        forbidden_read = client.get(
            f"/api/tasks/{task_id}",
            headers=headers_b,
        )
        assert forbidden_read.status_code == 404

        forbidden_update = client.patch(
            f"/api/tasks/{task_id}",
            json={"title": "Hacked task"},
            headers=headers_b,
        )
        assert forbidden_update.status_code == 404

        forbidden_delete = client.delete(
            f"/api/tasks/{task_id}",
            headers=headers_b,
        )
        assert forbidden_delete.status_code == 404

        # 8. Promote member B to admin
        update_user_role(settings, "member_b", "admin")
        headers_admin = login("member_b")

        # 9. Admin can see all tasks
        admin_page = client.get(
            "/api/tasks",
            headers=headers_admin,
        )
        assert admin_page.status_code == 200
        assert admin_page.json()["total"] == 2

        # 10. Admin can access and update member A's task
        admin_read = client.get(
            f"/api/tasks/{task_id}",
            headers=headers_admin,
        )
        assert admin_read.status_code == 200

        admin_update = client.patch(
            f"/api/tasks/{task_id}",
            json={"completed": True},
            headers=headers_admin,
        )
        assert admin_update.status_code == 200
        assert admin_update.json()["completed"] is True

        # 11. Admin can delete member A's task
        admin_delete = client.delete(
            f"/api/tasks/{task_id}",
            headers=headers_admin,
        )
        assert admin_delete.status_code == 204
