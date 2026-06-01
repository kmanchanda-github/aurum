from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request
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
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PortfolioDetail:
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

    # ── Fetch live prices for all unique symbols in parallel ──────────────────
    registry = getattr(request.app.state, "registry", None)
    unique_symbols = list({h.symbol.upper() for h in holdings})
    prices: dict[str, float] = {}
    day_changes: dict[str, tuple[float, float]] = {}  # symbol → (change, change_pct)

    if registry and unique_symbols:
        import asyncio
        async def _fetch(sym: str) -> None:
            try:
                quote = await registry.get_quote(sym)
                prices[sym] = quote.price
                day_changes[sym] = (quote.change, quote.change_pct)
            except Exception:
                pass  # leave missing — show cost basis only

        await asyncio.gather(*[_fetch(s) for s in unique_symbols])

    # ── Build per-holding details ──────────────────────────────────────────────
    holding_details: list[HoldingDetail] = []
    total_value = 0.0
    total_cost = 0.0
    allocation_map: dict[str, float] = {}

    for h in holdings:
        detail = HoldingDetail.model_validate(h)
        qty = float(h.quantity)
        cost_per_share = float(h.cost_basis)
        cost = qty * cost_per_share
        total_cost += cost

        sym = h.symbol.upper()
        if sym in prices:
            current_price = prices[sym]
            current_value = qty * current_price
            pnl = current_value - cost
            pnl_pct = (pnl / cost * 100) if cost else 0.0
            change, change_pct = day_changes.get(sym, (0.0, 0.0))

            detail.current_price = round(current_price, 2)
            detail.current_value = round(current_value, 2)
            detail.unrealized_pnl = round(pnl, 2)
            detail.unrealized_pnl_pct = round(pnl_pct, 2)
            detail.day_change = round(change, 2)
            detail.day_change_pct = round(change_pct, 2)
            total_value += current_value

            asset_class = h.asset_class or "other"
            allocation_map[asset_class] = allocation_map.get(asset_class, 0.0) + current_value
        else:
            # No live price — fall back to cost basis
            detail.current_price = cost_per_share
            detail.current_value = round(cost, 2)
            total_value += cost
            asset_class = h.asset_class or "other"
            allocation_map[asset_class] = allocation_map.get(asset_class, 0.0) + cost

        holding_details.append(detail)

    # ── Allocation slices ──────────────────────────────────────────────────────
    allocation: list[AllocationSlice] = [
        AllocationSlice(
            label=ac,
            weight=round(val / total_value, 4) if total_value else 0,
            value=round(val, 2),
        )
        for ac, val in sorted(allocation_map.items(), key=lambda x: -x[1])
    ]

    unrealized_pnl = total_value - total_cost
    return PortfolioDetail(
        id=portfolio.id,
        name=portfolio.name,
        created_at=portfolio.created_at,
        holdings=holding_details,
        total_value=round(total_value, 2),
        total_cost=round(total_cost, 2),
        unrealized_pnl=round(unrealized_pnl, 2),
        unrealized_pnl_pct=round(unrealized_pnl / total_cost * 100, 2) if total_cost else 0,
        allocation=allocation,
    )


@router.delete("/{portfolio_id}", status_code=204)
async def delete_portfolio(
    portfolio_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    result = await db.execute(
        select(Portfolio).where(Portfolio.id == portfolio_id, Portfolio.user_id == user.id)
    )
    portfolio = result.scalar_one_or_none()
    if not portfolio:
        raise HTTPException(404, "Portfolio not found")
    await db.delete(portfolio)
    await db.commit()


@router.get("/{portfolio_id}/holdings", response_model=list[HoldingOut])
async def list_holdings(
    portfolio_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[HoldingOut]:
    result = await db.execute(
        select(Portfolio).where(Portfolio.id == portfolio_id, Portfolio.user_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(404, "Portfolio not found")
    holdings_result = await db.execute(
        select(Holding).where(Holding.portfolio_id == portfolio_id)
    )
    return [HoldingOut.model_validate(h) for h in holdings_result.scalars()]


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
