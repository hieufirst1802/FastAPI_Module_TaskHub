import logging

from redis.asyncio import Redis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)


class Cache:
    def __init__(self, client: Redis | None, ttl: int):
        self.client = client
        self.ttl = ttl

    async def get(self, key: str) -> str | None:
        if self.client is None:
            return None
        try:
            value: str | None = await self.client.get(key)
            return value
        except RedisError:
            logger.warning("Cache read failed; using database")
            return None

    async def put(self, key: str, value: str) -> None:
        if self.client is not None:
            try:
                await self.client.set(key, value, ex=self.ttl)
            except RedisError:
                logger.warning("Cache write failed")
