from asyncio import Event, create_task
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError
from redis.exceptions import ConnectionError, TimeoutError

from app.core.cache import TaskCache
from app.core.config import Settings
from app.core.exceptions import NotFoundException
from app.enums import UserRole
from app.models.task import Task
from app.models.user import User
from app.schemas.pagination import Page
from app.schemas.task import TaskOut, TaskUpdate
from app.schemas.workspace import ProjectTaskOut
from app.services.task import TaskService


@pytest.fixture
def cached_service(redis):
    cache = TaskCache(redis, ttl=10, prefix="test:detail")
    repo = AsyncMock()
    task = Task(id=1, owner_id=7, title="Original", description="", completed=False)
    repo.get_by_owner.return_value = task
    repo.get.return_value = task
    user = User(id=7, username="owner", role=UserRole.MEMBER)
    return TaskService(repo, AsyncMock(), cache), repo, user, task


async def detail_key(cache, identifier=1):
    version = await cache.version(cache.task_version_key(identifier))
    assert version is not None
    return cache.task_detail_key(identifier, version)


async def test_cache_aside_hit_miss_expiry(cached_service, redis):
    service, repo, user, task = cached_service
    expected = TaskOut.model_validate(task)
    assert await service.get(1, user) == expected
    assert await service.get(1, user) == expected
    assert repo.get_by_owner.await_count == 1
    key = await detail_key(service.cache)
    assert redis.values[key][1] == 10
    redis.now = 10
    assert await service.get(1, user) == expected
    assert repo.get_by_owner.await_count == 2


async def test_cached_ownership_and_admin(cached_service):
    service, repo, user, _ = cached_service
    await service.get(1, user)
    other = User(id=8, role=UserRole.MEMBER)
    with pytest.raises(NotFoundException):
        await service.get(1, other)
    other.role = UserRole.ADMIN
    assert (await service.get(1, other)).id == 1
    assert repo.get_by_owner.await_count == 1


async def test_update_delete_rotate_generation_after_commit(cached_service, redis):
    service, repo, user, task = cached_service
    await service.get(1, user)
    initial_key = await detail_key(service.cache)
    repo.update.return_value = task
    await service.update(1, TaskUpdate(title="Changed"), user)
    updated_key = await detail_key(service.cache)
    assert initial_key != updated_key
    assert await redis.get(updated_key) is None

    task.title = "Changed"
    assert (await service.get(1, user)).title == "Changed"
    await service.delete(1, user)
    assert await detail_key(service.cache) != updated_key

    repo.get_by_owner.return_value = None
    with pytest.raises(NotFoundException):
        await service.get(1, user)
    assert await redis.get(await detail_key(service.cache)) is None


async def test_late_reader_cannot_repopulate_current_generation(cached_service):
    service, repo, user, task = cached_service
    read_started, release_reader = Event(), Event()

    async def slow_read(*args):
        read_started.set()
        await release_reader.wait()
        return task

    repo.get_by_owner.side_effect = slow_read
    reader = create_task(service.get(1, user))
    await read_started.wait()
    await service.cache.invalidate(1)
    release_reader.set()
    assert (await reader).title == "Original"

    repo.get_by_owner.side_effect = None
    task.title = "Updated"
    assert (await service.get(1, user)).title == "Updated"


async def test_project_task_is_authorized_on_every_read_and_never_cached(cached_service, redis):
    service, repo, user, task = cached_service
    task.project_id = 23
    assert (await service.get(1, user)).project_id == 23
    assert (await service.get(1, user)).project_id == 23
    assert repo.get_by_owner.await_count == 2
    assert service.workspace.project.await_count == 2
    assert await redis.get(await detail_key(service.cache)) is None
    service.workspace.project.side_effect = NotFoundException("Workspace not found")
    with pytest.raises(NotFoundException, match="Task not found"):
        await service.get(1, user)


async def test_failed_write_keeps_cache_and_missing_not_cached(cached_service, redis):
    service, repo, user, _ = cached_service
    await service.get(1, user)
    key = await detail_key(service.cache)
    repo.update.side_effect = RuntimeError("database failed")
    with pytest.raises(RuntimeError):
        await service.update(1, TaskUpdate(title="Changed"), user)
    assert await detail_key(service.cache) == key
    assert await redis.get(key) is not None
    repo.get_by_owner.return_value = None
    with pytest.raises(NotFoundException):
        await service.get(2, user)
    with pytest.raises(NotFoundException):
        await service.delete(2, user)
    with pytest.raises(NotFoundException):
        await service.update(2, TaskUpdate(title="X"), user)
    assert await redis.get(await detail_key(service.cache, 2)) is None


@pytest.mark.parametrize("error", [ConnectionError, TimeoutError, OSError])
async def test_redis_errors_fall_back(error, cached_service):
    service, repo, user, task = cached_service
    client = AsyncMock()
    for method in (client.get, client.set, client.aclose):
        method.side_effect = error("unavailable")
    service.cache = TaskCache(client, ttl=10, prefix="test:unavailable")
    assert await service.get(1, user) == TaskOut.model_validate(task)
    repo.update.return_value = task
    assert await service.update(1, TaskUpdate(title="X"), user) is task
    await service.delete(1, user)
    await service.cache.close()


@pytest.mark.parametrize(
    "payload",
    ["broken-json", "{}", '{"id":999,"owner_id":7,"title":"X","description":"","completed":false}'],
)
async def test_corrupt_cache_reloads_database(payload, cached_service, redis):
    service, _repo, user, task = cached_service
    key = await detail_key(service.cache)
    await redis.set(key, payload, ex=10)
    assert await service.get(1, user) == TaskOut.model_validate(task)
    assert TaskOut.model_validate_json(await redis.get(key)).id == 1


async def test_disabled_cache_and_cleanup(settings, redis):
    cache = TaskCache.from_settings(settings)
    assert cache.client is None
    assert await cache.get("disabled", TaskOut) is None
    await cache.invalidate(1)
    await cache.close()
    await TaskCache(redis, ttl=10, prefix="test:close").close()
    assert redis.closed


def test_positive_ttl_and_timeout(settings):
    for field in ("redis_cache_ttl", "redis_socket_timeout"):
        with pytest.raises(ValidationError) as exc:
            Settings(**{field: 0}, jwt_secret_key=settings.jwt_secret_key)
        assert exc.value.errors()[0]["loc"] == (field,)


async def test_project_cache_errors_are_best_effort():
    client = AsyncMock()
    for method in (client.get, client.set):
        method.side_effect = ConnectionError("down")
    cache = TaskCache(client, ttl=10, prefix="test:project")
    assert await cache.version(cache.project_version_key(1)) is None
    assert await cache.get("page-key", Page[ProjectTaskOut]) is None
    await cache.set("page-key", Page[ProjectTaskOut](items=[], total=0, page=1, limit=20))
    await cache.invalidate_project(1)
