"""Unit tests for portfolio_agent."""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage


def _make_mock_llm(content="Portfolio analysis result."):
    llm = MagicMock()
    llm.ainvoke = AsyncMock(return_value=AIMessage(content=content))
    return llm


@pytest.mark.asyncio
async def test_portfolio_agent_no_user_id():
    """With no user_id, skips DB and calls LLM with empty portfolio."""
    from src.agents.portfolio_agent import portfolio_agent

    mock_llm = _make_mock_llm()
    state = {
        "messages": [HumanMessage(content="analyze my portfolio")],
        "retrieved_docs": [],
    }
    with patch("src.agents.portfolio_agent.get_llm", return_value=mock_llm):
        result = await portfolio_agent(state)

    assert len(result["agent_results"]) == 1
    assert result["agent_results"][0]["agent"] == "portfolio"
    assert result["agent_results"][0]["content"] == "Portfolio analysis result."
    assert result["agent_results"][0]["citations"] == []


@pytest.mark.asyncio
async def test_portfolio_agent_db_error_graceful():
    """DB error is swallowed; LLM still called with fallback text."""
    from src.agents.portfolio_agent import portfolio_agent

    mock_llm = _make_mock_llm("Fallback response.")
    state = {
        "messages": [HumanMessage(content="what is my return?")],
        "user_id": "user-abc",
        "retrieved_docs": [],
    }

    with patch("src.agents.portfolio_agent.get_llm", return_value=mock_llm):
        with patch("src.agents.portfolio_agent.AsyncSessionLocal", side_effect=RuntimeError("DB down")):
            result = await portfolio_agent(state)

    assert result["agent_results"][0]["content"] == "Fallback response."


@pytest.mark.asyncio
async def test_portfolio_agent_with_holdings():
    """Full path: user with portfolio + holdings, registry provides prices."""
    from decimal import Decimal as D

    from src.agents.portfolio_agent import portfolio_agent
    from src.adapters.base import Quote
    from datetime import datetime, timezone

    # Mock DB session and models
    mock_portfolio = MagicMock()
    mock_portfolio.name = "My Portfolio"
    mock_portfolio.id = "port-1"

    mock_holding = MagicMock()
    mock_holding.symbol = "AAPL"
    mock_holding.quantity = D("10")
    mock_holding.cost_basis = D("150.00")

    mock_db = AsyncMock()
    mock_db.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db.__aexit__ = AsyncMock(return_value=False)
    mock_db.execute = AsyncMock()

    # First execute: portfolio; second: holdings
    port_result = MagicMock()
    port_result.scalar_one_or_none.return_value = mock_portfolio
    hold_result = MagicMock()
    hold_result.scalars.return_value = [mock_holding]
    mock_db.execute.side_effect = [port_result, hold_result]

    mock_registry = AsyncMock()
    mock_registry.get_quote = AsyncMock(return_value=Quote(
        symbol="AAPL", price=185.0, change=1.0, change_pct=0.5,
        volume=1000000, as_of=datetime.now(timezone.utc), source="yfinance"
    ))

    mock_llm = _make_mock_llm("You have AAPL holdings.")

    state = {
        "messages": [HumanMessage(content="how is my portfolio doing?")],
        "user_id": "user-abc",
        "retrieved_docs": [],
        "__registry__": mock_registry,
    }

    with patch("src.agents.portfolio_agent.get_llm", return_value=mock_llm):
        with patch("src.agents.portfolio_agent.AsyncSessionLocal", return_value=mock_db):
            result = await portfolio_agent(state)

    assert result["agent_results"][0]["agent"] == "portfolio"
    assert "AAPL" in mock_llm.ainvoke.call_args[0][0][1].content


@pytest.mark.asyncio
async def test_portfolio_agent_no_portfolio_found():
    """User exists but has no portfolio — returns 'No portfolio data available.'"""
    from src.agents.portfolio_agent import portfolio_agent

    mock_db = AsyncMock()
    mock_db.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db.__aexit__ = AsyncMock(return_value=False)
    port_result = MagicMock()
    port_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=port_result)

    mock_llm = _make_mock_llm("No portfolio to analyze.")
    state = {
        "messages": [HumanMessage(content="show my portfolio")],
        "user_id": "user-xyz",
        "retrieved_docs": [],
    }

    with patch("src.agents.portfolio_agent.get_llm", return_value=mock_llm):
        with patch("src.agents.portfolio_agent.AsyncSessionLocal", return_value=mock_db):
            result = await portfolio_agent(state)

    call_content = mock_llm.ainvoke.call_args[0][0][1].content
    assert "No portfolio data available" in call_content


@pytest.mark.asyncio
async def test_portfolio_agent_citations_from_rag():
    """retrieved_docs with source_title are surfaced as citations."""
    from src.agents.portfolio_agent import portfolio_agent

    mock_llm = _make_mock_llm("analysis")
    state = {
        "messages": [HumanMessage(content="rebalance suggestions")],
        "retrieved_docs": [
            {"source_title": "Rebalancing Guide", "source_url": "https://x.com", "content": "Rebalance annually."},
            {"source_title": "", "source_url": "", "content": "No title doc — should be excluded"},
        ],
    }

    with patch("src.agents.portfolio_agent.get_llm", return_value=mock_llm):
        result = await portfolio_agent(state)

    citations = result["agent_results"][0]["citations"]
    assert len(citations) == 1
    assert citations[0]["source_title"] == "Rebalancing Guide"
