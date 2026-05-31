"""Unit tests for all six specialized agents."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import HumanMessage


def _make_llm(content: str) -> MagicMock:
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content=content))
    return mock_llm


def _state(message: str, **kwargs) -> dict:
    return {"messages": [HumanMessage(content=message)], **kwargs}


# ── QA Agent ────────────────────────────────────────────────────────────────


@patch("src.agents.qa_agent.get_llm")
async def test_qa_agent_returns_answer(mock_get_llm):
    mock_get_llm.return_value = _make_llm("Compound interest grows your money exponentially.")
    from src.agents.qa_agent import qa_agent

    result = await qa_agent(_state("What is compound interest?"))

    assert "agent_results" in result
    assert len(result["agent_results"]) == 1
    res = result["agent_results"][0]
    assert res["agent"] == "qa"
    assert "compound" in res["content"].lower()
    assert isinstance(res["citations"], list)


@patch("src.agents.qa_agent.get_llm")
async def test_qa_agent_includes_rag_context(mock_get_llm):
    mock_get_llm.return_value = _make_llm("Diversification reduces risk.")
    from src.agents.qa_agent import qa_agent

    docs = [{"source_title": "Diversification Guide", "source_url": "", "content": "Spread your investments."}]
    result = await qa_agent(_state("Tell me about diversification", retrieved_docs=docs))

    citations = result["agent_results"][0]["citations"]
    assert any(c["source_title"] == "Diversification Guide" for c in citations)


@patch("src.agents.qa_agent.get_llm")
async def test_qa_agent_no_rag_docs_returns_empty_citations(mock_get_llm):
    mock_get_llm.return_value = _make_llm("Bonds are fixed income instruments.")
    from src.agents.qa_agent import qa_agent

    result = await qa_agent(_state("What are bonds?", retrieved_docs=[]))
    assert result["agent_results"][0]["citations"] == []


# ── Market Agent ─────────────────────────────────────────────────────────────


@patch("src.agents.market_agent.get_llm")
async def test_market_agent_no_registry_returns_result(mock_get_llm):
    mock_get_llm.return_value = _make_llm("Market data is temporarily unavailable.")
    from src.agents.market_agent import market_agent

    result = await market_agent(_state("What is AAPL trading at?"))

    assert "agent_results" in result
    res = result["agent_results"][0]
    assert res["agent"] == "market"
    assert "data" in res


@patch("src.agents.market_agent.get_llm")
async def test_market_agent_with_registry_fetches_quote(mock_get_llm):
    mock_get_llm.return_value = _make_llm("AAPL is trading at $175.")

    mock_quote = MagicMock()
    mock_quote.symbol = "AAPL"
    mock_quote.price = 175.0
    mock_quote.change = 1.5
    mock_quote.change_pct = 0.86
    mock_quote.week_52_high = 198.0
    mock_quote.week_52_low = 124.0

    mock_registry = MagicMock()
    mock_registry.get_quote = AsyncMock(return_value=mock_quote)

    from src.agents.market_agent import market_agent

    result = await market_agent(_state("What is AAPL trading at?", __registry__=mock_registry))
    res = result["agent_results"][0]
    snapshot = res["data"]["market_snapshot"]
    assert any("AAPL" in s for s in snapshot)


@patch("src.agents.market_agent.get_llm")
async def test_market_agent_registry_failure_is_handled(mock_get_llm):
    mock_get_llm.return_value = _make_llm("Market data unavailable.")

    mock_registry = MagicMock()
    mock_registry.get_quote = AsyncMock(side_effect=RuntimeError("API error"))

    from src.agents.market_agent import market_agent

    result = await market_agent(_state("What is SPY?", __registry__=mock_registry))
    assert result["agent_results"][0]["agent"] == "market"


# ── Portfolio Agent ───────────────────────────────────────────────────────────


@patch("src.agents.portfolio_agent.get_llm")
async def test_portfolio_agent_no_user_id(mock_get_llm):
    mock_get_llm.return_value = _make_llm("You have no portfolio data on record.")
    from src.agents.portfolio_agent import portfolio_agent

    result = await portfolio_agent(_state("Analyze my portfolio"))
    res = result["agent_results"][0]
    assert res["agent"] == "portfolio"
    assert isinstance(res["content"], str)


@patch("src.agents.portfolio_agent.get_llm")
async def test_portfolio_agent_returns_citations_from_rag(mock_get_llm):
    mock_get_llm.return_value = _make_llm("Your portfolio is concentrated in tech.")
    from src.agents.portfolio_agent import portfolio_agent

    docs = [{"source_title": "Asset Allocation", "source_url": "", "content": "Balance your holdings."}]
    result = await portfolio_agent(_state("Analyze my portfolio", retrieved_docs=docs))
    citations = result["agent_results"][0]["citations"]
    assert any(c["source_title"] == "Asset Allocation" for c in citations)


# ── Goals Agent ──────────────────────────────────────────────────────────────


@patch("src.agents.goals_agent.get_llm")
async def test_goals_agent_no_user_returns_result(mock_get_llm):
    mock_get_llm.return_value = _make_llm("To retire at 60 you need to save $2M.")
    from src.agents.goals_agent import goals_agent

    result = await goals_agent(_state("I want to retire at 60 with $2 million."))
    res = result["agent_results"][0]
    assert res["agent"] == "goals"
    assert isinstance(res["content"], str)
    assert len(res["content"]) > 0


@patch("src.agents.goals_agent.get_llm")
async def test_goals_agent_with_rag_context_includes_citations(mock_get_llm):
    mock_get_llm.return_value = _make_llm("Based on your goal, save $1,500/month.")
    from src.agents.goals_agent import goals_agent

    docs = [{"source_title": "Retirement Planning", "source_url": "", "content": "Start early and invest consistently."}]
    result = await goals_agent(_state("Help me plan for retirement", retrieved_docs=docs))
    citations = result["agent_results"][0]["citations"]
    assert any(c["source_title"] == "Retirement Planning" for c in citations)


# ── Tax Agent ────────────────────────────────────────────────────────────────


@patch("src.agents.tax_agent.get_llm")
@patch("src.agents.tax_agent.settings")
async def test_tax_agent_appends_disclaimer(mock_settings, mock_get_llm):
    mock_settings.disclaimer_text = "This is not financial advice."
    mock_settings.guardrails_config = {"disclaimer_enabled": True}
    mock_get_llm.return_value = _make_llm("A Roth IRA grows tax-free.")
    from src.agents.tax_agent import tax_agent

    result = await tax_agent(_state("What is a Roth IRA?"))
    content = result["agent_results"][0]["content"]
    assert "This is not financial advice." in content


@patch("src.agents.tax_agent.get_llm")
@patch("src.agents.tax_agent.settings")
async def test_tax_agent_disclaimer_disabled(mock_settings, mock_get_llm):
    mock_settings.disclaimer_text = "Not advice."
    mock_settings.guardrails_config = {"disclaimer_enabled": False}
    mock_get_llm.return_value = _make_llm("Capital gains are taxed at preferential rates.")
    from src.agents.tax_agent import tax_agent

    result = await tax_agent(_state("Explain capital gains tax"))
    content = result["agent_results"][0]["content"]
    assert "Not advice." not in content


# ── News Agent ───────────────────────────────────────────────────────────────


@patch("src.agents.news_agent.get_llm")
async def test_news_agent_no_registry_returns_result(mock_get_llm):
    mock_get_llm.return_value = _make_llm("No live news available right now.")
    from src.agents.news_agent import news_agent

    result = await news_agent(_state("What's happening in the markets today?"))
    res = result["agent_results"][0]
    assert res["agent"] == "news"
    assert isinstance(res["content"], str)


@patch("src.agents.news_agent.get_llm")
async def test_news_agent_with_registry_processes_articles(mock_get_llm):
    from datetime import datetime, timezone
    from src.adapters.base import NewsItem

    mock_get_llm.return_value = _make_llm("The Fed raised rates today, causing a market selloff.")

    sample_items = [
        NewsItem(
            title="Fed Raises Rates",
            url="https://example.com/1",
            source="Reuters",
            published_at=datetime.now(timezone.utc),
            summary="Federal Reserve raises rates.",
        ),
    ]
    mock_registry = MagicMock()
    mock_registry.fetch_news = AsyncMock(return_value=sample_items)

    from src.agents.news_agent import news_agent

    result = await news_agent(_state("Latest market news?", __registry__=mock_registry))
    assert result["agent_results"][0]["agent"] == "news"
