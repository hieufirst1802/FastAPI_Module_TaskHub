import sqlite3
from contextlib import closing

from alembic.script import ScriptDirectory
from sqlalchemy.engine import make_url


def test_health_and_migration(client, settings, migration_config):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

    config = migration_config(settings.database_url)
    expected_heads = set(ScriptDirectory.from_config(config).get_heads())
    database_path = make_url(settings.database_url).database
    with closing(sqlite3.connect(database_path)) as connection:
        revisions = connection.execute("SELECT version_num FROM alembic_version")
        assert {revision for (revision,) in revisions} == expected_heads


def test_openapi(client, tasks_url):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    assert paths[tasks_url]["post"]["summary"] == "Create a task"
    assert "404" in paths[f"{tasks_url}/{{task_id}}"]["patch"]["responses"]
