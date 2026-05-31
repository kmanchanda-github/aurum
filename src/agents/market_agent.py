"""Market analysis agent: real-time quotes, history, index data."""
from __future__ import annotations

import re
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage

from src.agents.rag import _last_user_message
from src.core.llm import get_llm
from src.core.logging import get_logger

logger = get_logger(__name__)
_PROMPT = (Path(__file__).parent / "prompts" / "market.txt").read_text()

_TICKER_RE = re.compile(r"\b([A-Z]{1,5})\b")
_COMMON_WORDS = {"I", "A", "AND", "OR", "THE", "IN", "AT", "FOR", "TO", "IS", "IT", "IF", "ME", "MY"}


def _extract_symbols(text: str) -> list[str]:
    found = _TICKER_RE.findall(text.upper())
    return [s for s in found if s not in _COMMON_WORDS and len(s) >= 2][:5]


async def market_agent(state: dict) -> dict:
    registry = state.get("__registry__")
    messages = state.get("messages", [])
    query = _last_user_message(messages)

    market_data_parts: list[str] = []

    # Fetch index data
    if registry:
        from src.core.config import settings
        for sym in settings.default_indices[:3]:
            try:
                q = await registry.get_quote(sym)
                sign = "+" if q.change >= 0 else ""
                market_data_parts.append(
                    f"**{q.symbol}**: ${q.price:.2f} ({sign}{q.change:.2f}, {sign}{q.change_pct:.2f}%)"
                )
            except Exception:
                pass

        # Extract any tickers mentioned in query
        symbols = _extract_symbols(query)
        for sym in symbols:
            try:
                q = await registry.get_quote(sym)
                sign = "+" if q.change >= 0 else ""
                market_data_parts.append(
                    f"**{sym}**: ${q.price:.2f} ({sign}{q.change:.2f}, {sign}{q.change_pct:.2f}%) "
                    f"| 52w High: ${q.week_52_high or 'N/A'} | 52w Low: ${q.week_52_low or 'N/A'}"
                )
            except Exception:
                pass

    market_context = "\n".join(market_data_parts) if market_data_parts else "Market data temporarily unavailable."

    llm = get_llm(streaming=True)
    response = await llm.ainvoke([
        SystemMessage(content=_PROMPT),
        HumanMessage(content=f"User question: {query}\n\n### Live Market Data\n{market_context}"),
    ])

    return {
        "agent_results": [
            {
                "agent": "market",
                "content": response.content,
                "citations": [],
                "data": {"market_snapshot": market_data_parts},
            }
        ]
    }
