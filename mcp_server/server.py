"""
Aurum MCP Server
================
Exposes Aurum's finance tools via the Model Context Protocol.

Default transport: stdio (Claude Desktop)
Remote transport:  streamable-http (set MCP_TRANSPORT=streamable-http)

Usage — Claude Desktop (stdio):
    python3 -m mcp_server.server

Usage — Remote HTTP:
    MCP_TRANSPORT=streamable-http python3 -m mcp_server.server
    MCP_TRANSPORT=streamable-http MCP_HOST=0.0.0.0 MCP_PORT=8002 python3 -m mcp_server.server

Claude Desktop config (~/.config/claude/claude_desktop_config.json):
    {
      "mcpServers": {
        "aurum-finance": {
          "command": "python3",
          "args": ["-m", "mcp_server.server"],
          "cwd": "/absolute/path/to/Aurum",
          "env": {
            "USE_IN_MEMORY_CACHE": "true"
          }
        }
      }
    }
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import Any

# ── Env defaults (before any Aurum imports trigger pydantic-settings) ─────────
os.environ.setdefault("USE_IN_MEMORY_CACHE", "true")
os.environ.setdefault("USE_SQLITE", "true")
os.environ.setdefault("SECRET_KEY", "mcp-server-placeholder-not-used-for-auth")

# Add project root to path so `src.*` imports work regardless of cwd
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastmcp import FastMCP

# ── Server instance ───────────────────────────────────────────────────────────

mcp = FastMCP(
    name="Aurum Finance Assistant",
    instructions=(
        "Financial education and market data tools. "
        "Use get_stock_quote for live prices, search_knowledge_base for education, "
        "analyze_portfolio for holdings analysis, and calculate_goal_projection "
        "for retirement/savings planning with Monte Carlo simulations."
    ),
)

# ── Lazy adapter singletons ───────────────────────────────────────────────────
# Initialised once on first use to avoid import cost at startup.

_yfinance_adapter = None
_news_adapter = None
_chroma_store = None
_cache: dict[str, Any] = {}  # simple in-process TTL cache dict


def _market() -> Any:
    global _yfinance_adapter
    if _yfinance_adapter is None:
        from src.adapters.market.yfinance_adapter import YFinanceAdapter
        _yfinance_adapter = YFinanceAdapter()
    return _yfinance_adapter


def _news() -> Any:
    global _news_adapter
    if _news_adapter is None:
        from src.adapters.news.pygooglenews_adapter import PyGoogleNewsAdapter
        _news_adapter = PyGoogleNewsAdapter()
    return _news_adapter


def _rag() -> Any:
    global _chroma_store
    if _chroma_store is None:
        from src.rag.chroma_store import ChromaStore
        _chroma_store = ChromaStore()
    return _chroma_store


# ── Tools ─────────────────────────────────────────────────────────────────────


@mcp.tool()
async def get_stock_quote(symbol: str) -> dict:
    """Get the current real-time stock quote for a ticker symbol.

    Returns price, change, percentage change, 52-week high/low, market cap,
    and volume. Data is sourced from Yahoo Finance via yfinance.

    Args:
        symbol: Ticker symbol (e.g. AAPL, MSFT, NVDA, BTC-USD, ^GSPC for S&P 500)
    """
    quote = await _market().get_quote(symbol.upper())
    return {
        "symbol": quote.symbol,
        "price": round(quote.price, 2),
        "change": round(quote.change, 2),
        "change_pct": round(quote.change_pct, 2),
        "volume": quote.volume,
        "market_cap": quote.market_cap,
        "week_52_high": quote.week_52_high,
        "week_52_low": quote.week_52_low,
        "as_of": quote.as_of.isoformat(),
        "source": quote.source,
    }


@mcp.tool()
async def get_market_overview() -> list[dict]:
    """Get a snapshot of major US market indices: S&P 500, NASDAQ, Dow Jones.

    Returns current price and daily change for each index.
    Useful for understanding overall market direction before discussing
    individual stocks or portfolio decisions.
    """
    indices = ["^GSPC", "^IXIC", "^DJI"]
    names = {"^GSPC": "S&P 500", "^IXIC": "NASDAQ Composite", "^DJI": "Dow Jones"}
    results = []
    for sym in indices:
        try:
            q = await _market().get_quote(sym)
            results.append({
                "name": names.get(sym, sym),
                "symbol": sym,
                "price": round(q.price, 2),
                "change": round(q.change, 2),
                "change_pct": round(q.change_pct, 2),
            })
        except Exception as e:
            results.append({"name": names.get(sym, sym), "symbol": sym, "error": str(e)})
    return results


@mcp.tool()
async def get_stock_history(
    symbol: str,
    period: str = "1mo",
    interval: str = "1d",
) -> dict:
    """Get historical OHLCV price data for a ticker symbol.

    Args:
        symbol: Ticker symbol (e.g. AAPL, TSLA)
        period: Time period — one of: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max
        interval: Bar interval — one of: 1d, 1wk, 1mo (use 1d for periods under 1 year)
    """
    bars = await _market().get_history(symbol.upper(), period=period, interval=interval)
    bar_list = [
        {
            "date": b.ts.strftime("%Y-%m-%d"),
            "open": round(b.open, 2),
            "high": round(b.high, 2),
            "low": round(b.low, 2),
            "close": round(b.close, 2),
            "volume": b.volume,
        }
        for b in bars
    ]
    if not bar_list:
        return {"symbol": symbol.upper(), "period": period, "bars": []}

    closes = [b["close"] for b in bar_list]
    total_return = ((closes[-1] - closes[0]) / closes[0] * 100) if closes[0] else 0

    return {
        "symbol": symbol.upper(),
        "period": period,
        "interval": interval,
        "bar_count": len(bar_list),
        "start_price": closes[0],
        "end_price": closes[-1],
        "total_return_pct": round(total_return, 2),
        "period_high": max(b["high"] for b in bar_list),
        "period_low": min(b["low"] for b in bar_list),
        "bars": bar_list[-30:],  # cap at 30 bars to keep response size manageable
    }


@mcp.tool()
async def search_financial_news(
    query: str,
    limit: int = 5,
) -> list[dict]:
    """Search for recent financial news articles matching a query.

    Returns article titles, sources, publication dates, and summaries.
    Useful for current events, earnings news, Fed decisions, sector trends.

    Args:
        query: Search query (e.g. "Federal Reserve interest rates", "Apple earnings", "inflation")
        limit: Number of articles to return (1–10)
    """
    limit = max(1, min(limit, 10))
    items = await _news().fetch(query=query, limit=limit)
    return [
        {
            "title": item.title,
            "source": item.source,
            "published_at": item.published_at.strftime("%Y-%m-%d %H:%M"),
            "url": item.url,
            "summary": item.summary,
        }
        for item in items
    ]


@mcp.tool()
def search_knowledge_base(
    query: str,
    categories: list[str] | None = None,
    k: int = 5,
) -> list[dict]:
    """Search Aurum's financial education knowledge base using semantic similarity.

    The knowledge base contains 51 curated articles covering investing fundamentals,
    portfolio management, market analysis, financial goal planning, and tax strategy.

    Args:
        query: Natural language question or topic (e.g. "how does compound interest work")
        categories: Optional filter — list of categories to search within.
                    Valid values: investing, portfolio, market, goals, tax
                    Leave None to search all categories.
        k: Number of passages to return (1–10, default 5)
    """
    valid_cats = {"investing", "portfolio", "market", "goals", "tax"}
    if categories:
        categories = [c for c in categories if c in valid_cats] or None

    k = max(1, min(k, 10))
    docs = _rag().query(query, categories=categories, k=k)

    return [
        {
            "source_title": d.metadata.get("source_title", ""),
            "category": d.metadata.get("category", ""),
            "source_url": d.metadata.get("source_url", ""),
            "passage": d.content[:600],  # first 600 chars of the chunk
        }
        for d in docs
    ]


@mcp.tool()
async def analyze_portfolio(
    holdings: list[dict],
) -> dict:
    """Analyze a stock portfolio: fetch live prices, calculate P&L, and show allocation.

    Args:
        holdings: List of holdings, each with:
            - symbol (str): Ticker symbol, e.g. "AAPL"
            - shares (float): Number of shares held
            - cost_basis (float): Average purchase price per share

    Example:
        holdings = [
            {"symbol": "AAPL", "shares": 10, "cost_basis": 150.00},
            {"symbol": "VTI",  "shares": 25, "cost_basis": 210.00},
            {"symbol": "BND",  "shares": 30, "cost_basis": 75.00},
        ]
    """
    if not holdings:
        return {"error": "No holdings provided"}

    rows = []
    total_cost = 0.0
    total_value = 0.0
    failed = []

    for h in holdings:
        symbol = str(h.get("symbol", "")).upper()
        shares = float(h.get("shares", 0))
        cost_basis = float(h.get("cost_basis", 0))
        if not symbol or shares <= 0:
            continue
        try:
            q = await _market().get_quote(symbol)
            cost = shares * cost_basis
            value = shares * q.price
            pnl = value - cost
            pnl_pct = (pnl / cost * 100) if cost else 0
            total_cost += cost
            total_value += value
            rows.append({
                "symbol": symbol,
                "shares": shares,
                "cost_basis": cost_basis,
                "current_price": round(q.price, 2),
                "market_value": round(value, 2),
                "cost": round(cost, 2),
                "pnl": round(pnl, 2),
                "pnl_pct": round(pnl_pct, 2),
                "day_change_pct": round(q.change_pct, 2),
            })
        except Exception as e:
            failed.append({"symbol": symbol, "error": str(e)})

    # Allocation percentages
    for row in rows:
        row["allocation_pct"] = round(row["market_value"] / total_value * 100, 1) if total_value else 0

    total_pnl = total_value - total_cost
    total_pnl_pct = (total_pnl / total_cost * 100) if total_cost else 0

    return {
        "holdings": sorted(rows, key=lambda x: x["market_value"], reverse=True),
        "summary": {
            "total_cost": round(total_cost, 2),
            "total_value": round(total_value, 2),
            "total_pnl": round(total_pnl, 2),
            "total_pnl_pct": round(total_pnl_pct, 2),
            "position_count": len(rows),
        },
        "failed_symbols": failed,
        "disclaimer": "For educational purposes only. Not personalized investment advice.",
    }


@mcp.tool()
def calculate_goal_projection(
    monthly_contribution: float,
    current_amount: float,
    target_amount: float,
    years: int,
    risk_tolerance: str = "moderate",
    monte_carlo_runs: int = 1000,
) -> dict:
    """Project a financial goal using Monte Carlo simulation.

    Simulates thousands of possible market paths to estimate the probability
    of reaching a savings target given regular contributions and a risk profile.

    Args:
        monthly_contribution: Amount invested each month (USD)
        current_amount: Amount already saved toward this goal (USD)
        target_amount: The savings target (USD)
        years: Number of years until the goal deadline
        risk_tolerance: "conservative" (5% return, 8% vol),
                        "moderate" (7% return, 12% vol),
                        "aggressive" (10% return, 18% vol)
        monte_carlo_runs: Number of simulation paths (100–5000, default 1000)
    """
    import numpy as np

    return_map = {"conservative": 0.05, "moderate": 0.07, "aggressive": 0.10}
    vol_map = {"conservative": 0.08, "moderate": 0.12, "aggressive": 0.18}

    risk_tolerance = risk_tolerance.lower()
    if risk_tolerance not in return_map:
        risk_tolerance = "moderate"

    annual_return = return_map[risk_tolerance]
    annual_vol = vol_map[risk_tolerance]
    monthly_return = annual_return / 12
    monthly_vol = annual_vol / (12 ** 0.5)
    months = years * 12
    monte_carlo_runs = max(100, min(monte_carlo_runs, 5000))

    rng = np.random.default_rng(seed=42)
    paths = np.zeros((monte_carlo_runs, months + 1))
    paths[:, 0] = current_amount

    shocks = rng.normal(monthly_return, monthly_vol, (monte_carlo_runs, months))
    for m in range(months):
        paths[:, m + 1] = paths[:, m] * (1 + shocks[:, m]) + monthly_contribution

    # Year-by-year percentiles
    projection = []
    for yr in range(1, years + 1):
        vals = paths[:, yr * 12]
        projection.append({
            "year": yr,
            "p10": round(float(np.percentile(vals, 10)), 0),
            "p50": round(float(np.percentile(vals, 50)), 0),
            "p90": round(float(np.percentile(vals, 90)), 0),
        })

    final = paths[:, -1]
    prob_success = float(np.mean(final >= target_amount))

    return {
        "inputs": {
            "monthly_contribution": monthly_contribution,
            "current_amount": current_amount,
            "target_amount": target_amount,
            "years": years,
            "risk_tolerance": risk_tolerance,
            "monte_carlo_runs": monte_carlo_runs,
        },
        "probability_of_success": round(prob_success, 3),
        "final_year": {
            "p10": round(float(np.percentile(final, 10)), 0),
            "p50": round(float(np.percentile(final, 50)), 0),
            "p90": round(float(np.percentile(final, 90)), 0),
        },
        "year_by_year": projection,
        "disclaimer": "Projections are educational illustrations only, not guaranteed outcomes.",
    }


@mcp.tool()
def ask_finance_question(question: str, categories: list[str] | None = None) -> dict:
    """Answer a financial education question using Aurum's knowledge base.

    Performs semantic search over 51 curated finance articles and returns
    the most relevant passages with source attribution. Use this when the
    user asks a conceptual question about investing, taxes, portfolio management,
    market dynamics, or financial goal planning.

    Args:
        question: The finance question to look up
        categories: Optional category filter (investing, portfolio, market, goals, tax)
    """
    valid_cats = {"investing", "portfolio", "market", "goals", "tax"}
    if categories:
        categories = [c for c in categories if c in valid_cats] or None

    docs = _rag().query(question, categories=categories, k=5)

    if not docs:
        return {
            "question": question,
            "passages": [],
            "note": "No relevant articles found. Try broader terms.",
        }

    passages = [
        {
            "source_title": d.metadata.get("source_title", "Unknown"),
            "category": d.metadata.get("category", ""),
            "content": d.content[:800],
        }
        for d in docs
    ]

    return {
        "question": question,
        "passages": passages,
        "disclaimer": "Educational content only — not personalized financial advice.",
    }


# ── Auth middleware for streamable-http transport ─────────────────────────────

_MCP_API_KEY = os.getenv("MCP_API_KEY", "")


async def _api_key_middleware(request, call_next):
    """Reject requests that don't carry the correct X-API-Key header (HTTP only)."""
    if _MCP_API_KEY:
        provided = request.headers.get("x-api-key", "")
        if provided != _MCP_API_KEY:
            from starlette.responses import JSONResponse
            return JSONResponse({"error": "Unauthorized"}, status_code=401)
    return await call_next(request)


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    transport = os.getenv("MCP_TRANSPORT", "stdio").lower()

    if transport == "stdio":
        mcp.run(transport="stdio")

    elif transport in ("streamable-http", "http"):
        host = os.getenv("MCP_HOST", "0.0.0.0")
        port = int(os.getenv("MCP_PORT", "8002"))

        if _MCP_API_KEY:
            mcp.add_middleware(_api_key_middleware)
            print(f"[aurum-mcp] API key auth enabled", flush=True)
        else:
            print(
                "[aurum-mcp] WARNING: MCP_API_KEY not set — server is open to anyone on the network.",
                flush=True,
            )

        print(f"[aurum-mcp] Starting streamable-http on {host}:{port}", flush=True)
        mcp.run(transport="streamable-http", host=host, port=port)

    else:
        print(f"[aurum-mcp] Unknown transport '{transport}'. Use 'stdio' or 'streamable-http'.", flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
