from unittest.mock import AsyncMock

from redis.exceptions import ConnectionError

from app.cache import Cache


async def test_cache_hit_ttl_and_outage():
    client = AsyncMock()
    client.get.return_value = "cached"
    cache = Cache(client, 30)
    assert await cache.get("key") == "cached"
    await cache.put("key", "value")
    client.set.assert_awaited_once_with("key", "value", ex=30)
    client.get.side_effect = ConnectionError("offline")
    client.set.side_effect = ConnectionError("offline")
    assert await cache.get("key") is None
    await cache.put("key", "value")
    assert await Cache(None, 30).get("key") is None
