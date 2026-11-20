import sqlite3
from contextlib import closing

from alembic.script import ScriptDirectory
from sqlalchemy.engine import make_url


def test_health_and_migration(public_client, settings, migration_config):
    response = public_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

    config = migration_config(settings.database_url)
    expected_heads = set(ScriptDirectory.from_config(config).get_heads())
    database_path = make_url(settings.database_url).database
    with closing(sqlite3.connect(database_path)) as connection:
        revisions = connection.execute("SELECT version_num FROM alembic_version")
        assert {revision for (revision,) in revisions} == expected_heads


def test_openapi(public_client, tasks_url):
    response = public_client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    assert paths[tasks_url]["post"]["summary"] == "Create a task"
    assert "404" in paths[f"{tasks_url}/{{task_id}}"]["patch"]["responses"]
    auth_operations = (
        ("/register", "post", {"409", "422"}),
        ("/login", "post", {"401", "422"}),
        ("/me", "get", {"401"}),
    )
    for suffix, method, response_codes in auth_operations:
        operation = paths[f"/api/v1/auth{suffix}"][method]
        assert operation["summary"]
        assert response_codes <= operation["responses"].keys()
