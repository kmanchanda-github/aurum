"""Unit tests for supervisor routing: parse success, fallback, filtering."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import HumanMessage

from src.agents.supervisor import supervisor_route


def _llm_returning(payload: dict) -> MagicMock:
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(
        return_value=MagicMock(content=json.dumps(payload))
    )
    return mock_llm


def _state_with(message: str) -> dict:
    return {"messages": [HumanMessage(content=message)]}


# ── Happy path ────────────────────────────────────────────────────────────────

@patch("src.agents.supervisor.get_llm")
async def test_routes_to_market_agent(mock_get_llm):
    mock_get_llm.return_value = _llm_returning({
        "intent": "stock price query",
        "selected_agents": ["market"],
        "rag_categories": ["market"],
        "routing_reason": "user asked for current price",
        "confidence": 0.95,
        "needs_clarification": False,
    })

    result = await supervisor_route(_state_with("What is AAPL trading at today?"))
    assert result["selected_agents"] == ["market"]
    assert result["rag_categories"] == ["market"]
    assert result["needs_followup"] is False


@patch("src.agents.supervisor.get_llm")
async def test_routes_to_multiple_agents(mock_get_llm):
    mock_get_llm.return_value = _llm_returning({
        "intent": "portfolio and market analysis",
        "selected_agents": ["portfolio", "market"],
        "rag_categories": ["portfolio", "market"],
        "routing_reason": "query spans portfolio and market",
        "confidence": 0.88,
        "needs_clarification": False,
    })

    result = await supervisor_route(_state_with("How is my portfolio vs the S&P today?"))
    assert set(result["selected_agents"]) == {"portfolio", "market"}


# ── Fallback on parse error ───────────────────────────────────────────────────

@patch("src.agents.supervisor.get_llm")
async def test_falls_back_to_qa_on_invalid_json(mock_get_llm):
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="NOT VALID JSON {{{"))
    mock_get_llm.return_value = mock_llm

    result = await supervisor_route(_state_with("Tell me about compound interest"))
    assert result["selected_agents"] == ["qa"]
    assert result["rag_categories"] == ["investing"]


@patch("src.agents.supervisor.get_llm")
async def test_falls_back_on_llm_exception(mock_get_llm):
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(side_effect=RuntimeError("LLM timeout"))
    mock_get_llm.return_value = mock_llm

    result = await supervisor_route(_state_with("hello"))
    assert result["selected_agents"] == ["qa"]


# ── Agent filtering ───────────────────────────────────────────────────────────

@patch("src.agents.supervisor.get_llm")
async def test_filters_out_invalid_agent_names(mock_get_llm):
    mock_get_llm.return_value = _llm_returning({
        "intent": "test",
        "selected_agents": ["market", "nonexistent_agent", "hacker"],
        "rag_categories": ["market"],
        "confidence": 0.9,
        "needs_clarification": False,
    })

    result = await supervisor_route(_state_with("show me stocks"))
    assert "nonexistent_agent" not in result["selected_agents"]
    assert "hacker" not in result["selected_agents"]
    assert "market" in result["selected_agents"]


@patch("src.agents.supervisor.get_llm")
async def test_defaults_to_qa_when_all_agents_invalid(mock_get_llm):
    mock_get_llm.return_value = _llm_returning({
        "intent": "test",
        "selected_agents": ["bad_agent"],
        "rag_categories": ["investing"],
        "confidence": 0.9,
        "needs_clarification": False,
    })

    result = await supervisor_route(_state_with("something"))
    assert result["selected_agents"] == ["qa"]


# ── Clarification trigger ─────────────────────────────────────────────────────

@patch("src.agents.supervisor.get_llm")
async def test_sets_needs_followup_for_low_confidence(mock_get_llm):
    mock_get_llm.return_value = _llm_returning({
        "intent": "unclear",
        "selected_agents": ["qa"],
        "rag_categories": ["investing"],
        "confidence": 0.4,
        "needs_clarification": False,
    })

    result = await supervisor_route(_state_with("do the thing"))
    assert result["needs_followup"] is True


@patch("src.agents.supervisor.get_llm")
async def test_strips_markdown_code_fences(mock_get_llm):
    payload = {
        "intent": "tax question",
        "selected_agents": ["tax"],
        "rag_categories": ["tax"],
        "confidence": 0.85,
        "needs_clarification": False,
    }
    # Simulate LLM wrapping response in markdown code block
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(
        return_value=MagicMock(content=f"```json\n{json.dumps(payload)}\n```")
    )
    mock_get_llm.return_value = mock_llm

    result = await supervisor_route(_state_with("What are capital gains taxes?"))
    assert result["selected_agents"] == ["tax"]
