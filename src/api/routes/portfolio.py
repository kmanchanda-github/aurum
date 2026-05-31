from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user, get_db
from src.models.portfolio import Holding, Portfolio
from src.models.user import User
from src.schemas.portfolio import (
    AllocationSlice,
    HoldingDetail,
    HoldingIn,
    HoldingOut,
    HoldingUpdate,
    PortfolioCreate,
    PortfolioDetail,
    PortfolioOut,
)

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


@router.get("", response_model=list[PortfolioOut])
async def list_portfolios(
    db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
) -> list[PortfolioOut]:
    result = await db.execute(select(Portfolio).where(Portfolio.user_id == user.id))
    return [PortfolioOut.model_validate(p) for p in result.scalars()]


@router.post("", response_model=PortfolioOut, status_code=201)
async def create_portfolio(
    body: PortfolioCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PortfolioOut:
    portfolio = Portfolio(user_id=user.id, name=body.name)
    db.add(portfolio)
    await db.commit()
    await db.refresh(portfolio)
    return PortfolioOut.model_validate(portfolio)


@router.get("/{portfolio_id}", response_model=PortfolioDetail)
async def get_portfolio(
    portfolio_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    request=None,
) -> PortfolioDetail:
    from fastapi import Request
    result = await db.execute(
        select(Portfolio).where(Portfolio.id == portfolio_id, Portfolio.user_id == user.id)
    )
    portfolio = result.scalar_one_or_none()
    if not portfolio:
        raise HTTPException(404, "Portfolio not found")

    holdings_result = await db.execute(
        select(Holding).where(Holding.portfolio_id == portfolio_id)
    )
    holdings = list(holdings_result.scalars())

    # Enrich with live prices via registry (best-effort)
    holding_details: list[HoldingDetail] = []
    total_value = 0.0
    total_cost = 0.0
    allocation_map: dict[str, float] = {}

    for h in holdings:
        detail = HoldingDetail.model_validate(h)
        cost = float(h.quantity) * float(h.cost_basis)
        total_cost += cost
        holding_details.append(detail)

    allocation: list[AllocationSlice] = []
    for ac, val in allocation_map.items():
        allocation.append(AllocationSlice(label=ac, weight=val / total_value if total_value else 0, value=val))

    return PortfolioDetail(
        id=portfolio.id,
        name=portfolio.name,
        created_at=portfolio.created_at,
        holdings=holding_details,
        total_value=total_value or total_cost,
        total_cost=total_cost,
        unrealized_pnl=total_value - total_cost,
        unrealized_pnl_pct=(total_value - total_cost) / total_cost * 100 if total_cost else 0,
        allocation=allocation,
    )


@router.post("/{portfolio_id}/holdings", response_model=HoldingOut, status_code=201)
async def add_holding(
    portfolio_id: str,
    body: HoldingIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> HoldingOut:
    result = await db.execute(
        select(Portfolio).where(Portfolio.id == portfolio_id, Portfolio.user_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(404, "Portfolio not found")

    holding = Holding(portfolio_id=portfolio_id, **body.model_dump())
    db.add(holding)
    await db.commit()
    await db.refresh(holding)
    return HoldingOut.model_validate(holding)


@router.patch("/{portfolio_id}/holdings/{holding_id}", response_model=HoldingOut)
async def update_holding(
    portfolio_id: str,
    holding_id: str,
    body: HoldingUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> HoldingOut:
    result = await db.execute(
        select(Holding).where(Holding.id == holding_id, Holding.portfolio_id == portfolio_id)
    )
    holding = result.scalar_one_or_none()
    if not holding:
        raise HTTPException(404, "Holding not found")

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(holding, field, value)
    await db.commit()
    await db.refresh(holding)
    return HoldingOut.model_validate(holding)


@router.delete("/{portfolio_id}/holdings/{holding_id}", status_code=204)
async def delete_holding(
    portfolio_id: str,
    holding_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    result = await db.execute(
        select(Holding).where(Holding.id == holding_id, Holding.portfolio_id == portfolio_id)
    )
    holding = result.scalar_one_or_none()
    if not holding:
        raise HTTPException(404, "Holding not found")
    await db.delete(holding)
    await db.commit()
