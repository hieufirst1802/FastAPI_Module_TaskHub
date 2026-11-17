from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError
from redis.exceptions import ConnectionError, TimeoutError

from app.core.cache import TaskCache
from app.core.config import Settings
from app.models.task import Task
from app.models.user import User
from app.schemas.task import TaskOut, TaskUpdate
from app.services.task import TaskService


class MemoryRedis:
    """Deterministic clock models Redis EX semantics without sleeping."""

    def __init__(self):
        self.now = 0
        self.values = {}
        self.closed = False

    async def get(self, key):
        value, expiry = self.values.get(key, (None, 0))
        return value if self.now < expiry else None

    async def set(self, key, value, ex):
        self.values[key] = (value, self.now + ex)

    async def delete(self, key):
        self.values.pop(key, None)

    async def aclose(self):
        self.closed = True


def setup_service():
    redis = MemoryRedis()
    cache = TaskCache(redis, ttl=10)
    repo = AsyncMock()
    task = Task(id=1, owner_id=7, title="Original", description="", completed=False)
    repo.get_by_owner.return_value = task
    repo.get.return_value = task
    user = User(id=7, username="owner", role="member")
    return TaskService(repo, cache), repo, redis, user, task


async def test_cache_aside_hit_miss_expiry():
    service, repo, redis, user, task = setup_service()
    assert await service.get(1, user) is task
    cached = await service.get(1, user)
    assert cached.title == "Original"
    assert repo.get_by_owner.await_count == 1
    assert redis.values[service.cache.key(1)][1] == 10
    redis.now = 10
    await service.get(1, user)
    assert repo.get_by_owner.await_count == 2


async def test_cached_ownership_and_admin():
    service, repo, _redis, user, _task = setup_service()
    await service.get(1, user)
    other = User(id=8, role="member")
    assert await service.get(1, other) is None
    other.role = "admin"
    assert (await service.get(1, other)).id == 1
    other.role = "member"
    assert await service.get(1, other) is None
    assert repo.get_by_owner.await_count == 1


async def test_update_delete_invalidate_after_commit():
    service, repo, redis, user, task = setup_service()
    await service.get(1, user)
    repo.update.return_value = task
    await service.update(1, TaskUpdate(title="Changed"), user)
    assert await redis.get(service.cache.key(1)) is None
    task.title = "Changed"
    assert (await service.get(1, user)).title == "Changed"
    assert await service.delete(1, user)
    assert await redis.get(service.cache.key(1)) is None
    repo.get_by_owner.return_value = None
    assert await service.get(1, user) is None
    assert not redis.values


async def test_failed_write_keeps_cache_and_missing_not_cached():
    service, repo, redis, user, _task = setup_service()
    await service.get(1, user)
    repo.update.side_effect = RuntimeError("database failed")
    with pytest.raises(RuntimeError):
        await service.update(1, TaskUpdate(title="Changed"), user)
    assert await redis.get(service.cache.key(1)) is not None
    repo.get_by_owner.return_value = None
    assert await service.get(2, user) is None
    assert not await service.delete(2, user)
    assert await service.update(2, TaskUpdate(title="X"), user) is None
    assert service.cache.key(2) not in redis.values


@pytest.mark.parametrize("error", [ConnectionError, TimeoutError, OSError])
async def test_redis_errors_fall_back(error):
    service, repo, _redis, user, task = setup_service()
    client = AsyncMock()
    for method in (client.get, client.set, client.delete, client.aclose):
        method.side_effect = error("unavailable")
    service.cache = TaskCache(client)
    assert await service.get(1, user) is task
    repo.update.return_value = task
    assert await service.update(1, TaskUpdate(title="X"), user) is task
    assert await service.delete(1, user)
    await service.cache.close()


@pytest.mark.parametrize(
    "payload",
    ["broken-json", "{}", '{"id":999,"owner_id":7,"title":"X","description":"","completed":false}'],
)
async def test_corrupt_cache_reloads_database(payload):
    service, _repo, redis, user, task = setup_service()
    await redis.set(service.cache.key(1), payload, ex=10)
    assert await service.get(1, user) is task
    assert TaskOut.model_validate_json(await redis.get(service.cache.key(1))).id == 1


async def test_disabled_cache_and_cleanup():
    cache = TaskCache.from_settings(Settings(redis_enabled=False))
    assert cache.client is None
    assert await cache.get(1) is None
    await cache.set(TaskOut(id=1, owner_id=1, title="X", description="", completed=False))
    await cache.invalidate(1)
    await cache.close()
    redis = MemoryRedis()
    await TaskCache(redis).close()
    assert redis.closed


def test_positive_ttl_and_timeout():
    with pytest.raises(ValidationError):
        Settings(redis_cache_ttl=0)
    with pytest.raises(ValidationError):
        Settings(redis_socket_timeout=0)


def test_api_crud_with_cache(tmp_path, monkeypatch):
    from test_app import test_crud_validation_and_pagination

    redis = MemoryRedis()
    cache = TaskCache(redis)
    monkeypatch.setattr(TaskCache, "from_settings", classmethod(lambda cls, settings: cache))
    test_crud_validation_and_pagination(tmp_path)
    assert redis.closed
    assert not redis.values


async def test_project_cache_errors_are_best_effort():
    from app.schemas.workspace import ProjectTaskPage

    client = AsyncMock()
    for method in (client.get, client.set):
        method.side_effect = ConnectionError("down")
    cache = TaskCache(client)
    assert await cache.project_version(1) is None
    assert await cache.get_page("page-key") is None
    await cache.set_page("page-key", ProjectTaskPage(items=[], total=0, page=1, limit=20))
    await cache.invalidate_project(1)
