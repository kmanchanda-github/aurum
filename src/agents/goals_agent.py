"""Financial goal planning agent."""
from __future__ import annotations

from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage

from src.agents.rag import format_rag_context, _last_user_message
from src.core.database import AsyncSessionLocal
from src.core.llm import get_llm
from src.core.logging import get_logger

logger = get_logger(__name__)
_PROMPT = (Path(__file__).parent / "prompts" / "goals.txt").read_text()


async def goals_agent(state: dict) -> dict:
    user_id = state.get("user_id", "")
    messages = state.get("messages", [])
    query = _last_user_message(messages)
    rag_context = format_rag_context(state.get("retrieved_docs", []))

    goals_context = "No goals found."
    if user_id:
        try:
            from sqlalchemy import select
            from src.models.goal import Goal

            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(Goal).where(Goal.user_id == user_id).order_by(Goal.priority).limit(5)
                )
                goals = list(result.scalars())

            if goals:
                lines = []
                for g in goals:
                    progress = float(g.current_amount) / float(g.target_amount) * 100 if g.target_amount else 0
                    lines.append(
                        f"- **{g.name}** ({g.goal_type}): Target ${float(g.target_amount):,.0f} "
                        f"by {g.target_date or 'open-ended'} | "
                        f"Saved ${float(g.current_amount):,.0f} ({progress:.0f}%) | "
                        f"Monthly contribution: ${float(g.monthly_contribution):,.0f} | "
                        f"Risk: {g.risk_tolerance}"
                    )
                goals_context = "\n".join(lines)
        except Exception as exc:
            logger.warning("goals agent db error", error=str(exc))

    user_content = f"User question: {query}\n\n### Financial Goals\n{goals_context}"
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
            {"agent": "goals", "content": response.content, "citations": citations, "data": None}
        ]
    }
