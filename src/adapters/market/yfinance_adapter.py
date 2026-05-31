"""Google Finance / Yahoo Finance adapter using the yfinance library.

yfinance is the most reliable free source for real-time quotes and history,
covering the same data as Google Finance (stocks, ETFs, indices, crypto).
No API key required.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from functools import partial

import yfinance as yf

from src.adapters.base import Bar, MarketDataAdapter, Quote


class YFinanceAdapter(MarketDataAdapter):
    name = "yfinance"
    capabilities = {"quote", "history", "fundamentals", "search"}

    def _sync_get_quote(self, symbol: str) -> Quote:
        ticker = yf.Ticker(symbol)
        info = ticker.fast_info
        # fast_info is a lightweight dict-like object
        price = float(getattr(info, "last_price", 0) or 0)
        prev_close = float(getattr(info, "previous_close", price) or price)
        change = price - prev_close
        change_pct = (change / prev_close * 100) if prev_close else 0.0

        return Quote(
            symbol=symbol,
            price=price,
            change=change,
            change_pct=change_pct,
            volume=int(getattr(info, "three_month_average_volume", 0) or 0),
            market_cap=float(getattr(info, "market_cap", 0) or 0) or None,
            week_52_high=float(getattr(info, "year_high", 0) or 0) or None,
            week_52_low=float(getattr(info, "year_low", 0) or 0) or None,
            as_of=datetime.now(timezone.utc),
            source=self.name,
        )

    def _sync_get_history(self, symbol: str, period: str, interval: str) -> list[Bar]:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period, interval=interval)
        bars: list[Bar] = []
        for ts, row in df.iterrows():
            bars.append(
                Bar(
                    ts=ts.to_pydatetime().replace(tzinfo=timezone.utc),
                    open=float(row["Open"]),
                    high=float(row["High"]),
                    low=float(row["Low"]),
                    close=float(row["Close"]),
                    volume=int(row.get("Volume", 0) or 0),
                )
            )
        return bars

    def _sync_search(self, query: str) -> list[dict]:
        results = yf.Search(query, max_results=10)
        out = []
        for r in (results.quotes or []):
            out.append({
                "symbol": r.get("symbol", ""),
                "name": r.get("shortname") or r.get("longname", ""),
                "exchange": r.get("exchange", ""),
                "asset_type": r.get("quoteType", "stock").lower(),
            })
        return out

    async def get_quote(self, symbol: str) -> Quote:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, partial(self._sync_get_quote, symbol))

    async def get_history(self, symbol: str, period: str = "1mo", interval: str = "1d") -> list[Bar]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, partial(self._sync_get_history, symbol, period, interval)
        )

    async def search_symbols(self, query: str) -> list[dict]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, partial(self._sync_search, query))
