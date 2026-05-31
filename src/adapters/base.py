"""Abstract base classes and shared data models for market data and news adapters."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime


from pydantic import BaseModel


class Quote(BaseModel):
    symbol: str
    price: float
    change: float
    change_pct: float
    volume: int | None = None
    market_cap: float | None = None
    pe_ratio: float | None = None
    week_52_high: float | None = None
    week_52_low: float | None = None
    as_of: datetime
    source: str


class Bar(BaseModel):
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int


class NewsItem(BaseModel):
    title: str
    url: str
    source: str
    published_at: datetime
    summary: str | None = None


class MarketDataAdapter(ABC):
    name: str = "base"
    capabilities: set[str] = set()

    @abstractmethod
    async def get_quote(self, symbol: str) -> Quote: ...

    @abstractmethod
    async def get_history(
        self, symbol: str, period: str = "1mo", interval: str = "1d"
    ) -> list[Bar]: ...

    async def get_index(self, symbol: str) -> Quote:
        return await self.get_quote(symbol)

    async def search_symbols(self, query: str) -> list[dict]:
        return []

    async def health_check(self) -> bool:
        try:
            await self.get_quote("AAPL")
            return True
        except Exception:
            return False


class NewsAdapter(ABC):
    name: str = "base"

    @abstractmethod
    async def fetch(
        self, query: str, since: datetime | None = None, limit: int = 10
    ) -> list[NewsItem]: ...

    async def health_check(self) -> bool:
        try:
            items = await self.fetch("markets", limit=1)
            return len(items) >= 0
        except Exception:
            return False
