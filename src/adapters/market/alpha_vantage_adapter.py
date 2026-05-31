"""Alpha Vantage market data adapter. Requires ALPHA_VANTAGE_API_KEY."""
from __future__ import annotations

from datetime import datetime, timezone

import httpx

from src.adapters.base import Bar, MarketDataAdapter, Quote
from src.core.config import settings


class AlphaVantageAdapter(MarketDataAdapter):
    name = "alpha_vantage"
    capabilities = {"quote", "history", "fundamentals"}
    BASE_URL = "https://www.alphavantage.co/query"

    def __init__(self) -> None:
        key = settings.alpha_vantage_api_key
        if not key:
            raise ValueError("ALPHA_VANTAGE_API_KEY is required for AlphaVantageAdapter")
        self._key = key.get_secret_value()

    async def get_quote(self, symbol: str) -> Quote:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                self.BASE_URL,
                params={"function": "GLOBAL_QUOTE", "symbol": symbol, "apikey": self._key},
            )
            r.raise_for_status()
            data = r.json().get("Global Quote", {})

        price = float(data.get("05. price", 0))
        change = float(data.get("09. change", 0))
        change_pct_str = data.get("10. change percent", "0%").replace("%", "")
        change_pct = float(change_pct_str)
        volume = int(data.get("06. volume", 0))

        return Quote(
            symbol=symbol,
            price=price,
            change=change,
            change_pct=change_pct,
            volume=volume,
            as_of=datetime.now(timezone.utc),
            source=self.name,
        )

    async def get_history(self, symbol: str, period: str = "1mo", interval: str = "1d") -> list[Bar]:
        func = "TIME_SERIES_DAILY" if interval == "1d" else "TIME_SERIES_WEEKLY"
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(
                self.BASE_URL,
                params={"function": func, "symbol": symbol, "outputsize": "compact", "apikey": self._key},
            )
            r.raise_for_status()
            data = r.json()

        key = "Time Series (Daily)" if interval == "1d" else "Weekly Time Series"
        series = data.get(key, {})
        bars: list[Bar] = []
        for date_str, vals in sorted(series.items())[-60:]:
            bars.append(
                Bar(
                    ts=datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc),
                    open=float(vals["1. open"]),
                    high=float(vals["2. high"]),
                    low=float(vals["3. low"]),
                    close=float(vals["4. close"]),
                    volume=int(vals.get("5. volume", 0)),
                )
            )
        return bars
