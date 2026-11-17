import sqlite3

from alembic import command
from alembic.config import Config

from app.core.config import get_settings


def test_upgrade_preserves_legacy_data_and_downgrade(tmp_path, monkeypatch):
    database = tmp_path / "migration.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{database.as_posix()}")
    get_settings.cache_clear()
    config = Config("alembic.ini")
    try:
        command.upgrade(config, "fdaf932d4a5a")
        with sqlite3.connect(database) as connection:
            connection.execute(
                "INSERT INTO users (id,username,password_hash,role) VALUES (1,'legacy','hash','member')"
            )
            connection.execute(
                "INSERT INTO tasks (id,title,description,completed,owner_id) VALUES (1,'Existing','',1,1)"
            )
        command.upgrade(config, "head")
        command.check(config)
        with sqlite3.connect(database) as connection:
            assert connection.execute(
                "SELECT username,full_name,is_active FROM users"
            ).fetchone() == ("legacy", "", 1)
            assert connection.execute(
                "SELECT title,status,priority,project_id FROM tasks"
            ).fetchone() == ("Existing", "DONE", "MEDIUM", None)
            assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
            definitions = connection.execute(
                "SELECT sql FROM sqlite_master WHERE name='tasks'"
            ).fetchone()[0]
            assert "ck_task_status" in definitions
        command.downgrade(config, "fdaf932d4a5a")
        with sqlite3.connect(database) as connection:
            assert connection.execute("SELECT title,completed,owner_id FROM tasks").fetchone() == (
                "Existing",
                1,
                1,
            )
        command.upgrade(config, "head")
        command.check(config)
    finally:
        get_settings.cache_clear()
