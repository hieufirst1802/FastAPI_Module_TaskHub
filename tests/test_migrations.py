import sqlite3

import pytest
from alembic import command


@pytest.mark.parametrize("starting_revision", ["fdaf932d4a5a", "6efbd1a2c410", "ab39fc81da27"])
def test_upgrade_preserves_legacy_data_and_downgrade(tmp_path, migration_config, starting_revision):
    database = tmp_path / "migration.db"
    config = migration_config(f"sqlite+aiosqlite:///{database.as_posix()}")
    command.upgrade(config, "fdaf932d4a5a")
    with sqlite3.connect(database) as connection:
        connection.execute(
            "INSERT INTO users (id,username,password_hash,role) VALUES (1,'legacy','hash','member')"
        )
        connection.execute(
            "INSERT INTO tasks (id,title,description,completed,owner_id) VALUES (1,'Existing','',1,1)"
        )
    command.upgrade(config, starting_revision)
    if starting_revision != "fdaf932d4a5a":
        with sqlite3.connect(database) as connection:
            connection.execute(
                "INSERT INTO tasks (title,description,status,owner_id) VALUES "
                "('In flight','','IN_PROGRESS',1)"
            )
    command.upgrade(config, "head")
    command.check(config)
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT username,full_name,is_active FROM users").fetchone() == (
            "legacy",
            "",
            1,
        )
        assert connection.execute(
            "SELECT title,status,priority,project_id FROM tasks"
        ).fetchone() == ("Existing", "DONE", "MEDIUM", None)
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        definitions = connection.execute(
            "SELECT sql FROM sqlite_master WHERE name='tasks'"
        ).fetchone()[0]
        assert "ck_task_status" in definitions
        if starting_revision != "fdaf932d4a5a":
            assert connection.execute(
                "SELECT status,completed FROM tasks WHERE title='In flight'"
            ).fetchone() == ("IN_PROGRESS", 0)
        assert connection.execute(
            "SELECT is_active FROM users WHERE username='demo'"
        ).fetchone() == (0,)
    command.downgrade(config, "fdaf932d4a5a")
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT title,completed,owner_id FROM tasks").fetchone() == (
            "Existing",
            1,
            1,
        )
    command.upgrade(config, "head")
    command.check(config)
