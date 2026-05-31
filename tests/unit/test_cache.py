"""Unit tests for the in-memory cache implementation."""
import pytest
from src.core.redis_client import _InMemoryCache


@pytest.fixture
def cache():
    return _InMemoryCache()


async def test_get_returns_none_for_missing_key(cache):
    assert await cache.get("nonexistent") is None


async def test_set_and_get_roundtrip(cache):
    await cache.set("greeting", "hello", ex=60)
    assert await cache.get("greeting") == "hello"


async def test_delete_removes_key(cache):
    await cache.set("temp", "data", ex=60)
    await cache.delete("temp")
    assert await cache.get("temp") is None


async def test_different_ttl_buckets_are_independent(cache):
    await cache.set("short", "quick", ex=10)
    await cache.set("long", "slow", ex=3600)
    assert await cache.get("short") == "quick"
    assert await cache.get("long") == "slow"


async def test_overwrite_key(cache):
    await cache.set("key", "first", ex=60)
    await cache.set("key", "second", ex=60)
    assert await cache.get("key") == "second"


async def test_close_does_not_raise(cache):
    await cache.close()  # Should be a no-op
