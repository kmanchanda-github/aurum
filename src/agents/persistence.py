"""Persist the final turn (agent results → final_response) into state."""
from __future__ import annotations

from src.core.logging import get_logger

logger = get_logger(__name__)


async def persist_turn(state: dict) -> dict:
    """
    Consolidate agent_results → final_response if synthesizer didn't run
    (single-agent path where synthesizer is skipped).
    The actual DB write happens in the WebSocket handler after the graph completes.
    """
    agent_results = state.get("agent_results", [])
    final_response = state.get("final_response")
    final_citations = state.get("final_citations", [])

    if not final_response and agent_results:
        result = agent_results[0]
        final_response = result.get("content", "")
        final_citations = result.get("citations", [])

    logger.info(
        "turn complete",
        agents=len(agent_results),
        response_len=len(final_response or ""),
        citations=len(final_citations),
    )

    return {
        "final_response": final_response,
        "final_citations": final_citations,
    }
