import asyncio

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import Settings
from app.main import create_app
from app.models import Base


def test_persistent_crud_and_pagination(tmp_path):
    url = f"sqlite+aiosqlite:///{tmp_path / 'lesson.db'}"

    async def prepare():
        engine = create_async_engine(url)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        await engine.dispose()

    asyncio.run(prepare())
    config = Settings(database_url=url, jwt_secret="test-secret-at-least-32-characters-long")
    with TestClient(create_app(config)) as client:
        response = client.post("/api/tasks", json={"title": "Database task"})
        assert response.status_code == 201
        identifier = response.json()["id"]
        assert client.get("/api/tasks?limit=1").json()["total"] == 1
        assert client.get("/api/tasks?limit=101").status_code == 422
        assert client.patch(f"/api/tasks/{identifier}", json={"completed": True}).status_code == 200
    # Restart app with the same DB: committed data persists.
    with TestClient(create_app(config)) as client:
        assert client.get(f"/api/tasks/{identifier}").json()["completed"] is True
        assert client.delete(f"/api/tasks/{identifier}").status_code == 204
        assert client.get(f"/api/tasks/{identifier}").status_code == 404
