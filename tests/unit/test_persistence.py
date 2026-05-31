"""Unit tests for the persist_turn graph node."""
from __future__ import annotations

import pytest


async def test_persist_turn_consolidates_single_result():
    from src.agents.persistence import persist_turn

    state = {
        "agent_results": [{"agent": "qa", "content": "Compound interest grows wealth.", "citations": []}],
        "final_response": None,
        "final_citations": [],
    }
    result = await persist_turn(state)

    assert result["final_response"] == "Compound interest grows wealth."
    assert result["final_citations"] == []


async def test_persist_turn_preserves_existing_final_response():
    """If synthesizer already set final_response, persist_turn leaves it unchanged."""
    from src.agents.persistence import persist_turn

    state = {
        "agent_results": [{"agent": "qa", "content": "Original.", "citations": []}],
        "final_response": "Already synthesized response.",
        "final_citations": [],
    }
    result = await persist_turn(state)

    assert result["final_response"] == "Already synthesized response."


async def test_persist_turn_carries_citations():
    from src.agents.persistence import persist_turn

    citations = [{"source_title": "Tax Guide", "source_url": "", "snippet": "..."}]
    state = {
        "agent_results": [{"agent": "tax", "content": "Tax info.", "citations": citations}],
        "final_response": None,
        "final_citations": [],
    }
    result = await persist_turn(state)

    assert result["final_citations"] == citations


async def test_persist_turn_empty_agent_results():
    """No agent results and no final_response → returns None gracefully."""
    from src.agents.persistence import persist_turn

    state = {"agent_results": [], "final_response": None, "final_citations": []}
    result = await persist_turn(state)

    assert result["final_response"] is None
    assert result["final_citations"] == []


async def test_persist_turn_returns_correct_keys():
    from src.agents.persistence import persist_turn

    state = {
        "agent_results": [{"agent": "market", "content": "AAPL at $175.", "citations": []}],
        "final_response": None,
        "final_citations": [],
    }
    result = await persist_turn(state)

    assert "final_response" in result
    assert "final_citations" in result
