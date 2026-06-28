"""Unit tests for redis_client (in-memory cache path)."""
from __future__ import annotations

import json

import pytest


@pytest.fixture(autouse=True)
def use_in_memory(monkeypatch):
    """Force in-memory cache for all tests in this file."""
    monkeypatch.setenv("USE_IN_MEMORY_CACHE", "true")
    # Reset the module-level singleton so each test starts fresh
    import src.core.redis_client as rc
    rc._cache_instance = None
    yield
    rc._cache_instance = None


@pytest.mark.asyncio
async def test_in_memory_set_get():
    from src.core.redis_client import get_cache
    cache = get_cache()
    await cache.set("key1", "hello", ex=60)
    val = await cache.get("key1")
    assert val == "hello"


@pytest.mark.asyncio
async def test_in_memory_missing_key_returns_none():
    from src.core.redis_client import get_cache
    cache = get_cache()
    assert await cache.get("nonexistent") is None


@pytest.mark.asyncio
async def test_in_memory_delete():
    from src.core.redis_client import get_cache
    cache = get_cache()
    await cache.set("del_key", "value", ex=60)
    await cache.delete("del_key")
    assert await cache.get("del_key") is None


@pytest.mark.asyncio
async def test_in_memory_close_is_noop():
    from src.core.redis_client import get_cache
    cache = get_cache()
    await cache.close()  # should not raise


@pytest.mark.asyncio
async def test_cached_get_returns_none_for_missing():
    from src.core.redis_client import cached_get
    assert await cached_get("missing-key") is None


@pytest.mark.asyncio
async def test_cached_set_and_get_json():
    from src.core.redis_client import cached_get, cached_set
    payload = {"price": 185.5, "symbol": "AAPL"}
    await cached_set("quote:AAPL", payload, ttl=60)
    result = await cached_get("quote:AAPL")
    assert result == payload


@pytest.mark.asyncio
async def test_cached_set_and_get_string():
    from src.core.redis_client import cached_get, cached_set
    await cached_set("raw-string", "plain text", ttl=60)
    result = await cached_get("raw-string")
    assert result == "plain text"


@pytest.mark.asyncio
async def test_cached_get_json_decode_error_returns_raw():
    """If stored value is not valid JSON, return it as-is."""
    from src.core.redis_client import get_cache, cached_get
    cache = get_cache()
    await cache.set("bad-json", "not {valid} json", ex=60)
    result = await cached_get("bad-json")
    assert result == "not {valid} json"


def test_make_cache_returns_in_memory():
    from src.core.redis_client import make_cache, _InMemoryCache
    cache = make_cache()
    assert isinstance(cache, _InMemoryCache)
