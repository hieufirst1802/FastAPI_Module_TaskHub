import asyncio

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


def test_crud_validation_and_pagination(tmp_path):
    settings = Settings(database_url=f"sqlite+aiosqlite:///{(tmp_path / 'test.db').as_posix()}")
    prepare_database(settings)

    with TestClient(create_app(settings)) as client:
        assert client.get("/health").json() == {"status": "ok"}

        invalid = client.post("/api/tasks", json={"title": " "})
        assert invalid.status_code == 422

        response = client.post(
            "/api/tasks",
            json={"title": "Learn routing"},
        )
        assert response.status_code == 201

        task = response.json()
        identifier = task["id"]

        assert task["title"] == "Learn routing"
        assert task["description"] == ""
        assert task["completed"] is False
        assert task["owner_id"] > 0

        second = client.post(
            "/api/tasks",
            json={
                "title": "Learn database",
                "description": "Practice SQLAlchemy",
            },
        )
        assert second.status_code == 201

        page = client.get("/api/tasks").json()
        assert len(page["items"]) == 2
        assert page["total"] == 2
        assert page["offset"] == 0
        assert page["limit"] == 20

        next_page = client.get("/api/tasks?offset=1&limit=1").json()
        assert len(next_page["items"]) == 1
        assert next_page["total"] == 2
        assert next_page["offset"] == 1
        assert next_page["limit"] == 1

        detail = client.get(f"/api/tasks/{identifier}")
        assert detail.status_code == 200
        assert detail.json()["title"] == "Learn routing"

        updated = client.patch(
            f"/api/tasks/{identifier}",
            json={"completed": True},
        )
        assert updated.status_code == 200
        assert updated.json()["completed"] is True

        null_update = client.patch(
            f"/api/tasks/{identifier}",
            json={"title": None},
        )
        assert null_update.status_code == 422

        assert client.delete(f"/api/tasks/{identifier}").status_code == 204
        assert client.get(f"/api/tasks/{identifier}").status_code == 404
        assert client.get("/openapi.json").status_code == 200


def test_database_persistence_across_app_restart(tmp_path):
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'persistent.db').as_posix()}"
    )
    prepare_database(settings)

    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/tasks",
            json={"title": "Persistent task"},
        )
        assert response.status_code == 201
        identifier = response.json()["id"]

    with TestClient(create_app(settings)) as client:
        response = client.get(f"/api/tasks/{identifier}")

        assert response.status_code == 200
        assert response.json()["title"] == "Persistent task"
