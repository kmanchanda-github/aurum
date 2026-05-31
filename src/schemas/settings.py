from datetime import datetime

from pydantic import BaseModel


class AdapterHealth(BaseModel):
    name: str
    enabled: bool
    healthy: bool
    latency_ms: float | None = None
    last_error: str | None = None


class SettingsOut(BaseModel):
    market_adapter_priority: list[str]
    news_adapter_priority: list[str]
    preferred_currency: str
    watchlist: list[str]
    adapters: list[AdapterHealth] = []


class SettingsUpdate(BaseModel):
    market_adapter_priority: list[str] | None = None
    news_adapter_priority: list[str] | None = None
    preferred_currency: str | None = None
    watchlist: list[str] | None = None
