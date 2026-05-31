from __future__ import annotations

import json
from typing import Any

from src.core.config import settings


class _InMemoryCache:
    """Minimal TTL cache used when USE_IN_MEMORY_CACHE=true (HF Spaces deploy)."""

    def __init__(self) -> None:
        from cachetools import TTLCache
        self._stores: dict[int, TTLCache] = {}

    def _store(self, ttl: int) -> Any:
        if ttl not in self._stores:
            from cachetools import TTLCache
            self._stores[ttl] = TTLCache(maxsize=2048, ttl=ttl)
        return self._stores[ttl]

    async def get(self, key: str) -> str | None:
        for store in self._stores.values():
            val = store.get(key)
            if val is not None:
                return val
        return None

    async def set(self, key: str, value: str, ex: int = 60) -> None:
        self._store(ex)[key] = value

    async def delete(self, key: str) -> None:
        for store in self._stores.values():
            store.pop(key, None)

    async def close(self) -> None:
        pass


class _RedisCache:
    def __init__(self) -> None:
        import redis.asyncio as aioredis
        self._client = aioredis.from_url(settings.redis_url, decode_responses=True)

    async def get(self, key: str) -> str | None:
        return await self._client.get(key)

    async def set(self, key: str, value: str, ex: int = 60) -> None:
        await self._client.set(key, value, ex=ex)

    async def delete(self, key: str) -> None:
        await self._client.delete(key)

    async def close(self) -> None:
        await self._client.aclose()


def make_cache() -> _InMemoryCache | _RedisCache:
    if settings.use_in_memory_cache:
        return _InMemoryCache()
    return _RedisCache()


# Module-level singleton; replaced at app startup via lifespan
_cache_instance: _InMemoryCache | _RedisCache | None = None


def get_cache() -> _InMemoryCache | _RedisCache:
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = make_cache()
    return _cache_instance


async def cached_get(key: str) -> Any | None:
    raw = await get_cache().get(key)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


async def cached_set(key: str, value: Any, ttl: int = 60) -> None:
    payload = json.dumps(value) if not isinstance(value, str) else value
    await get_cache().set(key, payload, ex=ttl)
