"""Unit tests for market data and news adapters and the adapter registry."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.adapters.base import Bar, NewsItem, Quote


# ── YFinance Adapter ──────────────────────────────────────────────────────────


@patch("src.adapters.market.yfinance_adapter.yf.Ticker")
async def test_yfinance_returns_quote(mock_ticker_cls):
    fast_info = MagicMock()
    fast_info.last_price = 175.0
    fast_info.previous_close = 173.5
    fast_info.three_month_average_volume = 80_000_000
    fast_info.market_cap = 2_700_000_000_000
    fast_info.year_high = 199.0
    fast_info.year_low = 124.0

    mock_ticker_cls.return_value.fast_info = fast_info

    from src.adapters.market.yfinance_adapter import YFinanceAdapter

    adapter = YFinanceAdapter()
    quote = await adapter.get_quote("AAPL")

    assert quote.symbol == "AAPL"
    assert quote.price == pytest.approx(175.0)
    assert quote.change == pytest.approx(1.5)
    assert quote.source == "yfinance"


@patch("src.adapters.market.yfinance_adapter.yf.Ticker")
async def test_yfinance_handles_zero_prev_close(mock_ticker_cls):
    fast_info = MagicMock()
    fast_info.last_price = 50.0
    fast_info.previous_close = 0  # edge case
    fast_info.three_month_average_volume = 1_000_000
    fast_info.market_cap = None
    fast_info.year_high = None
    fast_info.year_low = None

    mock_ticker_cls.return_value.fast_info = fast_info

    from src.adapters.market.yfinance_adapter import YFinanceAdapter

    adapter = YFinanceAdapter()
    quote = await adapter.get_quote("XYZ")
    assert quote.change_pct == 0.0  # no division by zero


# ── Adapter Registry ─────────────────────────────────────────────────────────


def _make_quote(symbol: str, price: float = 100.0) -> Quote:
    return Quote(
        symbol=symbol,
        price=price,
        change=0.5,
        change_pct=0.5,
        as_of=datetime.now(timezone.utc),
        source="test",
    )


async def test_registry_get_quote_uses_primary_adapter():
    from src.adapters.registry import AdapterRegistry

    mock_cache = MagicMock()
    mock_cache.get = AsyncMock(return_value=None)
    mock_cache.set = AsyncMock()

    mock_adapter = MagicMock()
    mock_adapter.name = "mock_market"
    mock_adapter.capabilities = {"quote"}
    mock_adapter.get_quote = AsyncMock(return_value=_make_quote("MSFT", 300.0))

    registry = AdapterRegistry(cache=mock_cache)
    registry.register_market(mock_adapter, priority=1)

    quote = await registry.get_quote("MSFT")
    assert quote.symbol == "MSFT"
    assert quote.price == pytest.approx(300.0)


async def test_registry_returns_cached_quote():
    from src.adapters.registry import AdapterRegistry

    cached_quote = _make_quote("TSLA", 250.0)

    mock_cache = MagicMock()
    mock_cache.get = AsyncMock(return_value=cached_quote.model_dump_json())
    mock_cache.set = AsyncMock()

    mock_adapter = MagicMock()
    mock_adapter.name = "primary"
    mock_adapter.get_quote = AsyncMock(side_effect=AssertionError("Should not call adapter when cached"))

    registry = AdapterRegistry(cache=mock_cache)
    registry.register_market(mock_adapter, priority=1)

    quote = await registry.get_quote("TSLA")
    assert quote.symbol == "TSLA"
    assert quote.price == pytest.approx(250.0)
    mock_adapter.get_quote.assert_not_called()


async def test_registry_falls_through_to_secondary_adapter_on_failure():
    from src.adapters.registry import AdapterRegistry

    mock_cache = MagicMock()
    mock_cache.get = AsyncMock(return_value=None)
    mock_cache.set = AsyncMock()

    failing_adapter = MagicMock()
    failing_adapter.name = "failing"
    failing_adapter.capabilities = {"quote"}
    failing_adapter.get_quote = AsyncMock(side_effect=RuntimeError("API down"))

    backup_adapter = MagicMock()
    backup_adapter.name = "backup"
    backup_adapter.capabilities = {"quote"}
    backup_adapter.get_quote = AsyncMock(return_value=_make_quote("AMZN", 175.0))

    registry = AdapterRegistry(cache=mock_cache)
    registry.register_market(failing_adapter, priority=1)
    registry.register_market(backup_adapter, priority=2)

    quote = await registry.get_quote("AMZN")
    assert quote.price == pytest.approx(175.0)
    assert quote.source == "test"


async def test_registry_list_enabled_returns_registered_adapters():
    from src.adapters.registry import AdapterRegistry

    mock_cache = MagicMock()
    mock_cache.get = AsyncMock(return_value=None)

    adapter = MagicMock()
    adapter.name = "yfinance"

    registry = AdapterRegistry(cache=mock_cache)
    registry.register_market(adapter, priority=1)

    enabled = registry.list_enabled()
    assert "yfinance" in enabled["market"]


# ── News Adapter ─────────────────────────────────────────────────────────────


async def test_news_adapter_registry_fetch_news():
    from src.adapters.registry import AdapterRegistry

    mock_cache = MagicMock()
    mock_cache.get = AsyncMock(return_value=None)
    mock_cache.set = AsyncMock()

    sample_items = [
        NewsItem(
            title="Fed Raises Rates",
            url="https://example.com/1",
            source="Reuters",
            published_at=datetime.now(timezone.utc),
            summary="Federal Reserve raises rates by 25bps.",
        )
    ]

    mock_news = MagicMock()
    mock_news.name = "test_news"
    mock_news.fetch = AsyncMock(return_value=sample_items)  # registry calls .fetch()

    registry = AdapterRegistry(cache=mock_cache)
    registry.register_news(mock_news, priority=1)

    items = await registry.fetch_news(query="Fed rates", limit=5)
    assert len(items) == 1
    assert items[0].title == "Fed Raises Rates"
