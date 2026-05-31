"""Adapter registry: priority-sorted, Redis/in-memory cached, fallthrough on failure."""
from __future__ import annotations

import json
from typing import Any

from src.adapters.base import Bar, MarketDataAdapter, NewsAdapter, NewsItem, Quote
from src.core.config import settings
from src.core.logging import get_logger

logger = get_logger(__name__)


class NoAdapterAvailable(Exception):
    pass


class AdapterRegistry:
    def __init__(self, cache: Any) -> None:
        self._market: dict[str, MarketDataAdapter] = {}
        self._news: dict[str, NewsAdapter] = {}
        self._market_priority: list[str] = []
        self._news_priority: list[str] = []
        self._cache = cache

    def register_market(self, adapter: MarketDataAdapter, priority: int = 100) -> None:
        self._market[adapter.name] = adapter
        self._market_priority = sorted(
            list(self._market.keys()),
            key=lambda n: priority if n == adapter.name else
            next((i * 10 for i, name in enumerate(self._market_priority) if name == n), 999),
        )
        if adapter.name not in self._market_priority:
            self._market_priority.append(adapter.name)

    def register_news(self, adapter: NewsAdapter, priority: int = 100) -> None:
        self._news[adapter.name] = adapter
        if adapter.name not in self._news_priority:
            self._news_priority.append(adapter.name)

    def primary_market(self) -> MarketDataAdapter:
        if not self._market_priority:
            raise NoAdapterAvailable("No market adapters registered")
        return self._market[self._market_priority[0]]

    def list_enabled(self) -> dict[str, dict]:
        return {
            "market": {n: {"name": n} for n in self._market_priority},
            "news": {n: {"name": n} for n in self._news_priority},
        }

    async def get_quote(self, symbol: str) -> Quote:
        cache_key = f"quote:{symbol.upper()}"
        cached = await self._cache.get(cache_key)
        if cached:
            return Quote.model_validate_json(cached)

        last_exc: Exception | None = None
        for name in self._market_priority:
            try:
                quote = await self._market[name].get_quote(symbol)
                await self._cache.set(cache_key, quote.model_dump_json(), ex=settings.cache_ttl_quote)
                return quote
            except Exception as exc:
                logger.warning("market adapter failed", adapter=name, symbol=symbol, error=str(exc))
                last_exc = exc

        raise NoAdapterAvailable(f"All market adapters failed for {symbol}") from last_exc

    async def get_history(self, symbol: str, period: str = "1mo", interval: str = "1d") -> list[Bar]:
        cache_key = f"history:{symbol.upper()}:{period}:{interval}"
        cached = await self._cache.get(cache_key)
        if cached:
            data = json.loads(cached)
            return [Bar.model_validate(b) for b in data]

        last_exc: Exception | None = None
        for name in self._market_priority:
            try:
                bars = await self._market[name].get_history(symbol, period, interval)
                await self._cache.set(
                    cache_key,
                    json.dumps([b.model_dump(mode="json") for b in bars]),
                    ex=settings.cache_ttl_history,
                )
                return bars
            except Exception as exc:
                logger.warning("history adapter failed", adapter=name, error=str(exc))
                last_exc = exc

        raise NoAdapterAvailable(f"All adapters failed for history {symbol}") from last_exc

    async def fetch_news(
        self, query: str, limit: int = 10
    ) -> list[NewsItem]:
        import hashlib
        cache_key = f"news:{hashlib.sha256(query.encode()).hexdigest()[:16]}:{limit}"
        cached = await self._cache.get(cache_key)
        if cached:
            data = json.loads(cached)
            return [NewsItem.model_validate(i) for i in data]

        for name in self._news_priority:
            try:
                items = await self._news[name].fetch(query, limit=limit)
                await self._cache.set(
                    cache_key,
                    json.dumps([i.model_dump(mode="json") for i in items]),
                    ex=settings.cache_ttl_news,
                )
                return items
            except Exception as exc:
                logger.warning("news adapter failed", adapter=name, error=str(exc))

        return []


def build_registry(cache: Any) -> AdapterRegistry:
    """Build and populate the registry from config.yaml settings."""
    registry = AdapterRegistry(cache=cache)
    ds = settings.data_sources_config
    ns = settings.news_sources_config

    # Market adapters
    if ds.get("yfinance", {}).get("enabled", True):
        from src.adapters.market.yfinance_adapter import YFinanceAdapter
        registry.register_market(YFinanceAdapter(), priority=ds["yfinance"].get("priority", 10))

    if ds.get("alpha_vantage", {}).get("enabled") and settings.alpha_vantage_api_key:
        try:
            from src.adapters.market.alpha_vantage_adapter import AlphaVantageAdapter
            registry.register_market(AlphaVantageAdapter(), priority=ds["alpha_vantage"].get("priority", 20))
        except Exception as exc:
            logger.warning("alpha_vantage adapter init failed", error=str(exc))

    # News adapters
    if ns.get("pygooglenews", {}).get("enabled", True):
        from src.adapters.news.pygooglenews_adapter import PyGoogleNewsAdapter
        cfg = ns.get("pygooglenews", {})
        registry.register_news(
            PyGoogleNewsAdapter(language=cfg.get("language", "en"), country=cfg.get("country", "US")),
            priority=10,
        )

    return registry
