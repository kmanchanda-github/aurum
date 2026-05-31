"""Supervisor node: routes the user query to the appropriate specialist agent(s)."""
from __future__ import annotations

import json
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage

from src.core.llm import get_llm
from src.core.logging import get_logger

logger = get_logger(__name__)

VALID_AGENTS = {"qa", "portfolio", "market", "goals", "news", "tax"}
VALID_CATEGORIES = {"investing", "portfolio", "tax", "goals", "market"}

_PROMPT = (Path(__file__).parent / "prompts" / "supervisor.txt").read_text()


async def supervisor_route(state: dict) -> dict:
    messages = state.get("messages", [])
    last_user = next(
        (m.content for m in reversed(messages) if hasattr(m, "type") and m.type == "human"),
        "",
    )
    if not last_user and messages:
        last_user = getattr(messages[-1], "content", "")

    llm = get_llm(temperature=0.1)
    try:
        response = await llm.ainvoke([
            SystemMessage(content=_PROMPT),
            HumanMessage(content=f"User message: {last_user}"),
        ])
        raw = response.content.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        decision = json.loads(raw)
    except Exception as exc:
        logger.warning("supervisor parse failed, using qa fallback", error=str(exc))
        decision = {
            "intent": last_user[:100],
            "selected_agents": ["qa"],
            "rag_categories": ["investing"],
            "routing_reason": "fallback",
            "confidence": 0.5,
            "needs_clarification": False,
        }

    selected = [a for a in decision.get("selected_agents", ["qa"]) if a in VALID_AGENTS]
    if not selected:
        selected = ["qa"]

    categories = [c for c in decision.get("rag_categories", []) if c in VALID_CATEGORIES]
    if not categories:
        categories = ["investing"]

    confidence = float(decision.get("confidence", 1.0))
    needs_clarification = decision.get("needs_clarification", False) or confidence < 0.6

    logger.info(
        "supervisor routed",
        agents=selected,
        categories=categories,
        confidence=confidence,
    )

    return {
        "intent": decision.get("intent", ""),
        "selected_agents": selected,
        "rag_categories": categories,
        "routing_reason": decision.get("routing_reason", ""),
        "confidence": confidence,
        "needs_followup": needs_clarification,
    }
