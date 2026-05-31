from datetime import datetime

from pydantic import BaseModel


class QuoteOut(BaseModel):
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

    model_config = {"from_attributes": True}


class BarOut(BaseModel):
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int


class SymbolSearchResult(BaseModel):
    symbol: str
    name: str
    exchange: str
    asset_type: str = "stock"
