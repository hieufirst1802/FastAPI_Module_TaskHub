import sqlite3
from contextlib import closing

from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.database import create_engine
from app.main import create_app


def test_database_persistence(settings, tasks_url, client, access_token):
    response = client.post(tasks_url, json={"title": "Persistent task"})
    assert response.status_code == 201
    task = response.json()

    with TestClient(create_app(settings)) as restarted_client:
        response = restarted_client.get(
            f"{tasks_url}/{task['id']}", headers={"Authorization": f"Bearer {access_token}"}
        )
        assert response.status_code == 200
        assert response.json() == task


def test_upgrade_preserves_existing_tasks_and_owner(tmp_path, migration_config):
    database = tmp_path / "legacy.db"
    config = migration_config(f"sqlite+aiosqlite:///{database.as_posix()}")
    command.upgrade(config, "fdaf932d4a5a")

    with closing(sqlite3.connect(database)) as connection, connection:
        connection.execute("INSERT INTO users VALUES (1, 'demo', 'disabled-login', 'member')")
        connection.executemany(
            "INSERT INTO tasks VALUES (?, ?, '', ?, 1)",
            [(1, "Planned", False), (2, "Finished", True)],
        )

    command.upgrade(config, "head")
    command.check(config)
    with closing(sqlite3.connect(database)) as connection:
        assert connection.execute(
            "SELECT id, username, password_hash, role, is_active FROM users"
        ).fetchall() == [(1, "demo", "disabled-login", "member", 0)]
        assert connection.execute(
            "SELECT id, status, owner_id FROM tasks ORDER BY id"
        ).fetchall() == [(1, "TODO", 1), (2, "DONE", 1)]
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []

    command.downgrade(config, "fdaf932d4a5a")
    with closing(sqlite3.connect(database)) as connection:
        assert connection.execute(
            "SELECT id, completed, owner_id FROM tasks ORDER BY id"
        ).fetchall() == [(1, 0, 1), (2, 1, 1)]


async def test_sqlite_cascades_owner_deletion(settings, task):
    engine = create_engine(settings.database_url)
    try:
        async with engine.begin() as connection:
            assert await connection.scalar(text("PRAGMA foreign_keys")) == 1
            await connection.execute(
                text("DELETE FROM users WHERE id = :id"), {"id": task["owner_id"]}
            )
            assert await connection.scalar(text("SELECT COUNT(*) FROM tasks")) == 0
    finally:
        await engine.dispose()
