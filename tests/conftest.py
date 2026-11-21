from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app

ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"


@pytest.fixture
def tasks_url():
    return "/api/v1/tasks"


@pytest.fixture
def migration_config():
    def make_config(database_url):
        config = Config(str(ALEMBIC_INI))
        config.attributes["database_url"] = database_url
        return config

    return make_config


@pytest.fixture
def settings(tmp_path, migration_config):
    settings = Settings(database_url=f"sqlite+aiosqlite:///{(tmp_path / 'test.db').as_posix()}")
    command.upgrade(migration_config(settings.database_url), "head")
    return settings


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as client:
        yield client


@pytest.fixture
def task(client, tasks_url):
    response = client.post(tasks_url, json={"title": "Learn routing"})
    assert response.status_code == 201
    return response.json()
