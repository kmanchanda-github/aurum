"""Portfolio analysis agent: analyzes user holdings with live prices."""
from __future__ import annotations

from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage

from src.agents.rag import format_rag_context, _last_user_message
from src.core.database import AsyncSessionLocal
from src.core.llm import get_llm
from src.core.logging import get_logger

logger = get_logger(__name__)
_PROMPT = (Path(__file__).parent / "prompts" / "portfolio.txt").read_text()


async def portfolio_agent(state: dict) -> dict:
    registry = state.get("__registry__")
    user_id = state.get("user_id", "")
    messages = state.get("messages", [])
    query = _last_user_message(messages)
    rag_context = format_rag_context(state.get("retrieved_docs", []))

    portfolio_context = "No portfolio data available."
    if user_id:
        try:
            from sqlalchemy import select
            from src.models.portfolio import Holding, Portfolio

            async with AsyncSessionLocal() as db:
                port_result = await db.execute(
                    select(Portfolio).where(Portfolio.user_id == user_id).limit(1)
                )
                portfolio = port_result.scalar_one_or_none()

                if portfolio:
                    hold_result = await db.execute(
                        select(Holding).where(Holding.portfolio_id == portfolio.id)
                    )
                    holdings = list(hold_result.scalars())

                    lines = [f"Portfolio: **{portfolio.name}**\n"]
                    total_cost = 0.0
                    total_value = 0.0
                    for h in holdings:
                        cost = float(h.quantity) * float(h.cost_basis)
                        total_cost += cost
                        current_price = None
                        if registry:
                            try:
                                q = await registry.get_quote(h.symbol)
                                current_price = q.price
                                total_value += float(h.quantity) * q.price
                                pnl = (q.price - float(h.cost_basis)) * float(h.quantity)
                                pnl_pct = (q.price / float(h.cost_basis) - 1) * 100
                                lines.append(
                                    f"- {h.symbol}: {float(h.quantity):.2f} shares @ cost ${float(h.cost_basis):.2f} | "
                                    f"Current ${q.price:.2f} | P&L ${pnl:+.2f} ({pnl_pct:+.1f}%)"
                                )
                            except Exception:
                                lines.append(
                                    f"- {h.symbol}: {float(h.quantity):.2f} shares @ ${float(h.cost_basis):.2f}"
                                )
                        else:
                            lines.append(
                                f"- {h.symbol}: {float(h.quantity):.2f} shares @ ${float(h.cost_basis):.2f}"
                            )
                    if total_cost:
                        tv = total_value or total_cost
                        pnl = tv - total_cost
                        lines.append(f"\n**Total Cost**: ${total_cost:,.2f}")
                        lines.append(f"**Total Value**: ${tv:,.2f}")
                        lines.append(f"**Unrealized P&L**: ${pnl:+,.2f} ({pnl/total_cost*100:+.1f}%)")
                    portfolio_context = "\n".join(lines)
        except Exception as exc:
            logger.warning("portfolio agent db error", error=str(exc))

    user_content = f"User question: {query}\n\n### Portfolio Data\n{portfolio_context}"
    if rag_context:
        user_content += f"\n\n{rag_context}"

    llm = get_llm(streaming=True)
    response = await llm.ainvoke([
        SystemMessage(content=_PROMPT),
        HumanMessage(content=user_content),
    ])

    citations = [
        {"source_title": d.get("source_title", ""), "source_url": d.get("source_url", ""), "snippet": d.get("content", "")[:150]}
        for d in state.get("retrieved_docs", []) if d.get("source_title")
    ]

    return {
        "agent_results": [
            {"agent": "portfolio", "content": response.content, "citations": citations, "data": None}
        ]
    }
