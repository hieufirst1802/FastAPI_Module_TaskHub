"""Best-effort async cache. SQL remains the source of truth."""

import logging
from uuid import uuid4

from pydantic import ValidationError
from redis.asyncio import Redis
from redis.asyncio.retry import Retry
from redis.backoff import NoBackoff
from redis.exceptions import RedisError

from app.core.config import Settings
from app.schemas.task import TaskOut
from app.schemas.workspace import ProjectTaskPage

logger = logging.getLogger(__name__)


class TaskCache:
    def __init__(self, client: Redis | None, ttl: int = 60, prefix: str = "taskhub:v1") -> None:
        self.client = client
        self.ttl = ttl
        self.prefix = prefix

    @classmethod
    def from_settings(cls, settings: Settings) -> "TaskCache":
        client = None
        if settings.redis_enabled:
            client = Redis.from_url(
                settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=settings.redis_socket_timeout,
                socket_timeout=settings.redis_socket_timeout,
                retry=Retry(NoBackoff(), 0),
            )
        return cls(client, settings.redis_cache_ttl, settings.redis_key_prefix)

    def key(self, identifier: int) -> str:
        return f"{self.prefix}:tasks:{identifier}"

    async def get(self, identifier: int) -> TaskOut | None:
        if self.client is None:
            return None
        try:
            payload = await self.client.get(self.key(identifier))
            if payload is None:
                return None
            task = TaskOut.model_validate_json(payload)
            if task.id != identifier:
                await self.invalidate(identifier)
                return None
            return task
        except ValidationError:
            logger.warning("Invalid task cache payload; loading database")
            await self.invalidate(identifier)
        except (RedisError, OSError):
            logger.warning("Redis read unavailable; loading database")
        return None

    async def set(self, task: TaskOut) -> None:
        if self.client is None:
            return
        try:
            await self.client.set(self.key(task.id), task.model_dump_json(), ex=self.ttl)
        except (RedisError, OSError):
            logger.warning("Redis write unavailable; skipping cache")

    async def invalidate(self, identifier: int) -> None:
        if self.client is None:
            return
        try:
            await self.client.delete(self.key(identifier))
        except (RedisError, OSError):
            logger.warning("Redis invalidation unavailable; stale entry expires by TTL")

    async def close(self) -> None:
        if self.client is not None:
            try:
                await self.client.aclose()
            except (RedisError, OSError):
                logger.warning("Redis close failed")

    async def project_version(self, pid: int) -> str | None:
        if self.client is None:
            return None
        try:
            return await self.client.get(f"{self.prefix}:projects:{pid}:version") or "0"
        except (RedisError, OSError):
            logger.warning("Redis version unavailable; loading database")
            return None

    async def invalidate_project(self, pid: int) -> None:
        if self.client is None:
            return
        try:
            await self.client.set(
                f"{self.prefix}:projects:{pid}:version", uuid4().hex, ex=self.ttl * 2
            )
        except (RedisError, OSError):
            logger.warning("Redis project invalidation failed; stale entries expire by TTL")

    async def get_page(self, key: str) -> ProjectTaskPage | None:
        if self.client is None:
            return None
        try:
            payload = await self.client.get(key)
            return ProjectTaskPage.model_validate_json(payload) if payload is not None else None
        except (ValidationError, RedisError, OSError):
            logger.warning("Project cache unavailable or invalid; loading database")
            return None

    async def set_page(self, key: str, page: ProjectTaskPage) -> None:
        if self.client is not None:
            try:
                await self.client.set(key, page.model_dump_json(), ex=self.ttl)
            except (RedisError, OSError):
                logger.warning("Redis project cache write failed")
