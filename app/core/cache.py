"""Best-effort async cache. SQL remains the source of truth."""

import logging
from hashlib import sha256
from json import dumps
from uuid import uuid4

from pydantic import BaseModel, ValidationError
from redis.asyncio import Redis
from redis.asyncio.retry import Retry
from redis.backoff import NoBackoff
from redis.exceptions import RedisError

from app.core.config import Settings

logger = logging.getLogger(__name__)
VERSION_TTL_MULTIPLIER = 2


class TaskCache:
    def __init__(self, client: Redis | None, ttl: int, prefix: str) -> None:
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

    def task_version_key(self, task_id: int) -> str:
        return f"{self.prefix}:tasks:{task_id}:version"

    def task_detail_key(self, task_id: int, version: str) -> str:
        return f"{self.prefix}:tasks:{task_id}:standalone:{version}"

    def project_version_key(self, project_id: int) -> str:
        return f"{self.prefix}:projects:{project_id}:version"

    def standalone_version_key(self) -> str:
        return f"{self.prefix}:tasks:standalone:version"

    def page_key(
        self,
        scope: str,
        version: str,
        *parameters: str | int | bool | None,
    ) -> str:
        digest = sha256(dumps(parameters).encode()).hexdigest()
        return f"{self.prefix}:{scope}:page:{version}:{digest}"

    async def version(self, key: str) -> str | None:
        if self.client is None:
            return None
        try:
            current = await self.client.get(key)
            if isinstance(current, str):
                return current
            initial = uuid4().hex
            if await self.client.set(key, initial, ex=self.ttl * VERSION_TTL_MULTIPLIER, nx=True):
                return initial
            current = await self.client.get(key)
            return current if isinstance(current, str) else None
        except (RedisError, OSError):
            logger.warning("Redis version unavailable; loading database")
            return None

    async def bump_version(self, key: str) -> None:
        if self.client is None:
            return
        try:
            await self.client.set(key, uuid4().hex, ex=self.ttl * VERSION_TTL_MULTIPLIER)
        except (RedisError, OSError):
            logger.warning("Redis invalidation unavailable; stale entries expire by TTL")

    async def invalidate(self, task_id: int) -> None:
        await self.bump_version(self.task_version_key(task_id))

    async def invalidate_project(self, project_id: int) -> None:
        await self.bump_version(self.project_version_key(project_id))

    async def get[T: BaseModel](self, key: str, schema: type[T]) -> T | None:
        if self.client is None:
            return None
        try:
            payload = await self.client.get(key)
            return schema.model_validate_json(payload) if payload is not None else None
        except (RedisError, OSError, ValidationError):
            logger.warning("Cache unavailable or invalid; loading database")
            return None

    async def set(self, key: str, value: BaseModel) -> None:
        if self.client is None:
            return
        try:
            await self.client.set(key, value.model_dump_json(), ex=self.ttl)
        except (RedisError, OSError):
            logger.warning("Redis write unavailable; skipping cache")

    async def close(self) -> None:
        if self.client is not None:
            try:
                await self.client.aclose()
            except (RedisError, OSError):
                logger.warning("Redis close failed")
