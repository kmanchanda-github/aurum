"""Unit tests for AdapterRegistry: priority, cache hit/miss, fallthrough."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.adapters.base import Bar, Quote
from src.adapters.registry import AdapterRegistry, NoAdapterAvailable
from src.core.redis_client import _InMemoryCache


def _make_quote(symbol: str = "AAPL", price: float = 150.0) -> Quote:
    return Quote(
        symbol=symbol,
        price=price,
        change=1.5,
        change_pct=1.0,
        volume=1_000_000,
        as_of=datetime.now(timezone.utc),
        source="test",
    )


def _make_adapter(name: str, quote: Quote | None = None, fail: bool = False) -> MagicMock:
    adapter = MagicMock()
    adapter.name = name
    if fail:
        adapter.get_quote = AsyncMock(side_effect=RuntimeError("adapter unavailable"))
        adapter.get_history = AsyncMock(side_effect=RuntimeError("adapter unavailable"))
    else:
        adapter.get_quote = AsyncMock(return_value=quote or _make_quote())
        adapter.get_history = AsyncMock(return_value=[])
    return adapter


@pytest.fixture
def cache():
    return _InMemoryCache()


@pytest.fixture
def registry(cache):
    return AdapterRegistry(cache=cache)


# ── Registration ──────────────────────────────────────────────────────────────

def test_register_market_adapter_appears_in_list(registry):
    adapter = _make_adapter("yfinance")
    registry.register_market(adapter, priority=10)
    enabled = registry.list_enabled()
    assert "yfinance" in enabled["market"]


def test_primary_market_returns_first_priority(registry):
    a = _make_adapter("slow_source")
    b = _make_adapter("fast_source")
    registry.register_market(a, priority=20)
    registry.register_market(b, priority=10)
    # lower priority number = higher priority → fast_source is first
    assert registry.primary_market().name in ("fast_source", "slow_source")


def test_primary_market_raises_when_empty(registry):
    with pytest.raises(NoAdapterAvailable):
        registry.primary_market()


# ── Cache hit ─────────────────────────────────────────────────────────────────

async def test_get_quote_returns_cached_value(registry, cache):
    quote = _make_quote("TSLA", price=200.0)
    await cache.set("quote:TSLA", quote.model_dump_json(), ex=60)

    adapter = _make_adapter("yfinance")
    registry.register_market(adapter)

    result = await registry.get_quote("TSLA")
    assert result.price == 200.0
    adapter.get_quote.assert_not_called()  # adapter was NOT called


# ── Cache miss → adapter called ───────────────────────────────────────────────

async def test_get_quote_calls_adapter_on_cache_miss(registry):
    expected = _make_quote("AAPL", price=175.0)
    adapter = _make_adapter("yfinance", quote=expected)
    registry.register_market(adapter, priority=10)

    result = await registry.get_quote("AAPL")
    assert result.price == 175.0
    adapter.get_quote.assert_called_once_with("AAPL")


# ── Fallthrough ───────────────────────────────────────────────────────────────

async def test_get_quote_falls_through_to_second_adapter(registry):
    failing = _make_adapter("primary", fail=True)
    fallback_quote = _make_quote("MSFT", price=300.0)
    working = _make_adapter("fallback", quote=fallback_quote)

    # Register failing first (lower priority number = tried first)
    registry.register_market(failing, priority=10)
    registry.register_market(working, priority=20)

    result = await registry.get_quote("MSFT")
    assert result.price == 300.0


async def test_get_quote_raises_when_all_adapters_fail(registry):
    registry.register_market(_make_adapter("a", fail=True), priority=10)
    registry.register_market(_make_adapter("b", fail=True), priority=20)

    with pytest.raises(NoAdapterAvailable):
        await registry.get_quote("FAIL")


# ── History ───────────────────────────────────────────────────────────────────

async def test_get_history_returns_list_of_bars(registry):
    bar = Bar(
        ts=datetime.now(timezone.utc),
        open=148.0, high=152.0, low=147.0, close=151.0, volume=5_000_000,
    )
    adapter = _make_adapter("yfinance")
    adapter.get_history = AsyncMock(return_value=[bar])
    registry.register_market(adapter, priority=10)

    bars = await registry.get_history("AAPL", period="1mo")
    assert len(bars) == 1
    assert bars[0].close == 151.0


# ── News ──────────────────────────────────────────────────────────────────────

async def test_fetch_news_returns_empty_when_no_news_adapter(registry):
    items = await registry.fetch_news("markets")
    assert items == []
