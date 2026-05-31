from fastapi import APIRouter, Depends, Query, Request

from src.api.deps import get_current_user
from src.models.user import User
from src.schemas.market import BarOut, QuoteOut, SymbolSearchResult

router = APIRouter(prefix="/api/market", tags=["market"])


@router.get("/quote/{symbol}", response_model=QuoteOut)
async def get_quote(
    symbol: str,
    request: Request,
    user: User = Depends(get_current_user),
) -> QuoteOut:
    registry = request.app.state.registry
    quote = await registry.get_quote(symbol.upper())
    return QuoteOut(**quote.model_dump())


@router.get("/history/{symbol}", response_model=list[BarOut])
async def get_history(
    symbol: str,
    request: Request,
    period: str = Query("1mo", pattern="^(1d|5d|1mo|3mo|6mo|1y|2y|5y|10y|ytd|max)$"),
    interval: str = Query("1d", pattern="^(1m|2m|5m|15m|30m|60m|90m|1h|1d|5d|1wk|1mo|3mo)$"),
    user: User = Depends(get_current_user),
) -> list[BarOut]:
    registry = request.app.state.registry
    bars = await registry.get_history(symbol.upper(), period=period, interval=interval)
    return [BarOut(**b.model_dump()) for b in bars]


@router.get("/indices", response_model=list[QuoteOut])
async def get_indices(
    request: Request,
    user: User = Depends(get_current_user),
) -> list[QuoteOut]:
    from src.core.config import settings

    registry = request.app.state.registry
    results = []
    for sym in settings.default_indices:
        try:
            q = await registry.get_quote(sym)
            results.append(QuoteOut(**q.model_dump()))
        except Exception:
            pass
    return results


@router.get("/search", response_model=list[SymbolSearchResult])
async def search_symbols(
    q: str = Query(..., min_length=1),
    request: Request = None,
    user: User = Depends(get_current_user),
) -> list[SymbolSearchResult]:
    registry = request.app.state.registry
    try:
        results = await registry.primary_market().search_symbols(q)
        return [SymbolSearchResult(**r) for r in results]
    except Exception:
        return []


@router.get("/movers", response_model=list[QuoteOut])
async def get_movers(
    type: str = Query("gainers", pattern="^(gainers|losers|active)$"),
    request: Request = None,
    user: User = Depends(get_current_user),
) -> list[QuoteOut]:
    # yfinance doesn't have a direct movers API; return popular symbols as placeholder
    symbols = ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "JPM"]
    registry = request.app.state.registry
    results = []
    for sym in symbols:
        try:
            q = await registry.get_quote(sym)
            results.append(QuoteOut(**q.model_dump()))
        except Exception:
            pass
    if type == "gainers":
        results.sort(key=lambda x: x.change_pct, reverse=True)
    elif type == "losers":
        results.sort(key=lambda x: x.change_pct)
    return results[:5]
