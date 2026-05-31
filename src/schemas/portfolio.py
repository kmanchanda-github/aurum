from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel


class HoldingIn(BaseModel):
    symbol: str
    quantity: Decimal
    cost_basis: Decimal
    purchase_date: date | None = None
    asset_class: Literal["stock", "etf", "bond", "cash", "crypto", "other"] = "stock"
    notes: str | None = None


class HoldingUpdate(BaseModel):
    quantity: Decimal | None = None
    cost_basis: Decimal | None = None
    purchase_date: date | None = None
    asset_class: str | None = None
    notes: str | None = None


class HoldingOut(BaseModel):
    id: str
    symbol: str
    quantity: Decimal
    cost_basis: Decimal
    purchase_date: date | None
    asset_class: str
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class HoldingDetail(HoldingOut):
    current_price: float | None = None
    current_value: float | None = None
    unrealized_pnl: float | None = None
    unrealized_pnl_pct: float | None = None
    day_change: float | None = None
    day_change_pct: float | None = None


class AllocationSlice(BaseModel):
    label: str
    weight: float
    value: float


class PortfolioOut(BaseModel):
    id: str
    name: str
    created_at: datetime

    model_config = {"from_attributes": True}


class PortfolioCreate(BaseModel):
    name: str = "My Portfolio"


class PortfolioDetail(PortfolioOut):
    holdings: list[HoldingDetail] = []
    total_value: float = 0.0
    total_cost: float = 0.0
    unrealized_pnl: float = 0.0
    unrealized_pnl_pct: float = 0.0
    allocation: list[AllocationSlice] = []


class PerformancePoint(BaseModel):
    date: str
    value: float
    benchmark: float | None = None
