from pathlib import Path
from secrets import token_hex

import pytest
from alembic import command
from alembic.config import Config

from app.core.config import Settings


@pytest.fixture
def migration_config():
    def configure(database_url):
        config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        config.attributes.update(database_url=database_url, configure_logger=False)
        return config

    return configure


@pytest.fixture
def settings(tmp_path, migration_config):
    config = Settings(
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'test.db').as_posix()}",
        jwt_secret_key=token_hex(32),
        redis_enabled=False,
        log_level="INFO",
    )
    command.upgrade(migration_config(config.database_url), "head")
    return config


class MemoryRedis:
    """Deterministic clock models Redis expiration without sleeping."""

    def __init__(self):
        self.now = 0
        self.values = {}
        self.closed = False

    async def get(self, key):
        value, expiry = self.values.get(key, (None, 0))
        return value if self.now < expiry else None

    async def set(self, key, value, ex, nx=False):
        if nx and await self.get(key) is not None:
            return None
        self.values[key] = (value, self.now + ex)
        return True

    async def aclose(self):
        self.closed = True


@pytest.fixture
def redis():
    return MemoryRedis()
