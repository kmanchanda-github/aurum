"""Unit tests for goals_agent."""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage


def _make_mock_llm(content="Goal analysis."):
    llm = MagicMock()
    llm.ainvoke = AsyncMock(return_value=AIMessage(content=content))
    return llm


@pytest.mark.asyncio
async def test_goals_agent_no_user_id():
    """With no user_id, skips DB and answers with 'No goals found.'"""
    from src.agents.goals_agent import goals_agent

    mock_llm = _make_mock_llm()
    state = {
        "messages": [HumanMessage(content="how are my goals?")],
        "retrieved_docs": [],
    }
    with patch("src.agents.goals_agent.get_llm", return_value=mock_llm):
        result = await goals_agent(state)

    assert result["agent_results"][0]["agent"] == "goals"
    assert "No goals found" in mock_llm.ainvoke.call_args[0][0][1].content


@pytest.mark.asyncio
async def test_goals_agent_with_goals():
    """User with goals — DB rows passed through LLM prompt."""
    from src.agents.goals_agent import goals_agent

    mock_goal = MagicMock()
    mock_goal.name = "Retirement"
    mock_goal.goal_type = "retirement"
    mock_goal.target_amount = Decimal("1000000")
    mock_goal.current_amount = Decimal("150000")
    mock_goal.monthly_contribution = Decimal("2000")
    mock_goal.target_date = "2045-01-01"
    mock_goal.risk_tolerance = "moderate"
    mock_goal.priority = 1

    mock_db = AsyncMock()
    mock_db.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db.__aexit__ = AsyncMock(return_value=False)
    result_mock = MagicMock()
    result_mock.scalars.return_value = [mock_goal]
    mock_db.execute = AsyncMock(return_value=result_mock)

    mock_llm = _make_mock_llm("Retirement goal on track.")
    state = {
        "messages": [HumanMessage(content="am I on track for retirement?")],
        "user_id": "user-1",
        "retrieved_docs": [],
    }

    with patch("src.agents.goals_agent.get_llm", return_value=mock_llm):
        with patch("src.agents.goals_agent.AsyncSessionLocal", return_value=mock_db):
            result = await goals_agent(state)

    call_content = mock_llm.ainvoke.call_args[0][0][1].content
    assert "Retirement" in call_content
    assert result["agent_results"][0]["content"] == "Retirement goal on track."


@pytest.mark.asyncio
async def test_goals_agent_db_error_graceful():
    """DB failure swallowed; LLM called with 'No goals found.'"""
    from src.agents.goals_agent import goals_agent

    mock_llm = _make_mock_llm()
    state = {
        "messages": [HumanMessage(content="my goals")],
        "user_id": "user-1",
        "retrieved_docs": [],
    }

    with patch("src.agents.goals_agent.get_llm", return_value=mock_llm):
        with patch("src.agents.goals_agent.AsyncSessionLocal", side_effect=RuntimeError("DB down")):
            result = await goals_agent(state)

    assert "No goals found" in mock_llm.ainvoke.call_args[0][0][1].content


@pytest.mark.asyncio
async def test_goals_agent_no_goals_returned():
    """DB query returns empty list — 'No goals found.' in prompt."""
    from src.agents.goals_agent import goals_agent

    mock_db = AsyncMock()
    mock_db.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db.__aexit__ = AsyncMock(return_value=False)
    result_mock = MagicMock()
    result_mock.scalars.return_value = []
    mock_db.execute = AsyncMock(return_value=result_mock)

    mock_llm = _make_mock_llm()
    state = {
        "messages": [HumanMessage(content="show my goals")],
        "user_id": "user-2",
        "retrieved_docs": [],
    }

    with patch("src.agents.goals_agent.get_llm", return_value=mock_llm):
        with patch("src.agents.goals_agent.AsyncSessionLocal", return_value=mock_db):
            result = await goals_agent(state)

    assert "No goals found" in mock_llm.ainvoke.call_args[0][0][1].content
