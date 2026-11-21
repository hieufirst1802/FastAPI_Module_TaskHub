from pathlib import Path
from secrets import token_hex

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from pydantic import SecretStr

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
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'test.db').as_posix()}",
        jwt_secret_key=SecretStr(token_hex(32)),
        jwt_algorithm="HS256",
        access_token_expire_minutes=7,
    )
    command.upgrade(migration_config(settings.database_url), "head")
    return settings


@pytest.fixture
def public_client(settings):
    with TestClient(create_app(settings)) as client:
        yield client


@pytest.fixture
def account():
    return {"username": "task_owner", "password": "example-test-password"}


@pytest.fixture
def registered_user(public_client, account):
    response = public_client.post("/api/v1/auth/register", json=account)
    assert response.status_code == 201
    return response.json()


@pytest.fixture
def access_token(public_client, account, registered_user):
    response = public_client.post("/api/v1/auth/login", json=account)
    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    return response.json()["access_token"]


@pytest.fixture
def client(public_client, access_token):
    public_client.headers["Authorization"] = f"Bearer {access_token}"
    return public_client


@pytest.fixture
def task(client, tasks_url):
    response = client.post(tasks_url, json={"title": "Learn routing"})
    assert response.status_code == 201
    return response.json()
