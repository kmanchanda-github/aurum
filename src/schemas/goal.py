from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel


class GoalCreate(BaseModel):
    name: str
    goal_type: Literal["retirement", "house", "education", "emergency", "custom"] = "custom"
    target_amount: Decimal
    current_amount: Decimal = Decimal("0")
    monthly_contribution: Decimal = Decimal("0")
    target_date: date | None = None
    risk_tolerance: Literal["conservative", "moderate", "aggressive"] = "moderate"
    priority: int = 1
    notes: str | None = None


class GoalUpdate(BaseModel):
    name: str | None = None
    target_amount: Decimal | None = None
    current_amount: Decimal | None = None
    monthly_contribution: Decimal | None = None
    target_date: date | None = None
    risk_tolerance: str | None = None
    priority: int | None = None
    notes: str | None = None


class GoalOut(BaseModel):
    id: str
    name: str
    goal_type: str
    target_amount: Decimal
    current_amount: Decimal
    monthly_contribution: Decimal
    target_date: date | None
    risk_tolerance: str
    priority: int
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ProjectionPoint(BaseModel):
    year: int
    p10: float
    p50: float
    p90: float


class ProjectionResponse(BaseModel):
    goal_id: str
    years: int
    target_amount: float
    projection: list[ProjectionPoint]
    probability_of_success: float
