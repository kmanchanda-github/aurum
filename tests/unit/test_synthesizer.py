"""Unit tests for the synthesizer agent — covers all branches."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import HumanMessage


def _state(message: str, agent_results: list[dict], **kw) -> dict:
    return {"messages": [HumanMessage(content=message)], "agent_results": agent_results, **kw}


# ── Single-agent passthrough ──────────────────────────────────────────────────


async def test_synthesizer_single_agent_passthrough():
    """One agent result → no LLM call, content passed through directly."""
    from src.agents.synthesizer import synthesizer

    result = await synthesizer(_state(
        "What is an ETF?",
        [{"agent": "qa", "content": "An ETF is an exchange-traded fund.", "citations": []}],
    ))

    assert result["final_response"] == "An ETF is an exchange-traded fund."
    assert result["final_citations"] == []


async def test_synthesizer_single_agent_carries_citations():
    from src.agents.synthesizer import synthesizer

    citations = [{"source_title": "ETF Guide", "source_url": "", "snippet": "An ETF..."}]
    result = await synthesizer(_state(
        "What is an ETF?",
        [{"agent": "qa", "content": "Answer here.", "citations": citations}],
    ))

    assert result["final_citations"] == citations


# ── Multi-agent synthesis ─────────────────────────────────────────────────────


@patch("src.agents.synthesizer.get_llm")
@patch("src.agents.synthesizer.settings")
async def test_synthesizer_merges_two_agents(mock_settings, mock_get_llm):
    mock_settings.guardrails_config = {"disclaimer_enabled": False}
    mock_settings.disclaimer_text = "Not advice."
    mock_get_llm.return_value = MagicMock(
        ainvoke=AsyncMock(return_value=MagicMock(content="Combined answer."))
    )

    from src.agents.synthesizer import synthesizer

    result = await synthesizer(_state(
        "Market and portfolio question",
        [
            {"agent": "market", "content": "AAPL is at $175.", "citations": []},
            {"agent": "portfolio", "content": "Your portfolio is 60% tech.", "citations": []},
        ],
    ))

    assert result["final_response"] == "Combined answer."
    assert result["final_citations"] == []


@patch("src.agents.synthesizer.get_llm")
@patch("src.agents.synthesizer.settings")
async def test_synthesizer_deduplicates_citations(mock_settings, mock_get_llm):
    mock_settings.guardrails_config = {"disclaimer_enabled": False}
    mock_settings.disclaimer_text = "Not advice."
    mock_get_llm.return_value = MagicMock(
        ainvoke=AsyncMock(return_value=MagicMock(content="Synthesized."))
    )

    from src.agents.synthesizer import synthesizer

    shared_citation = {"source_title": "Diversification Guide", "source_url": "", "snippet": "..."}
    result = await synthesizer(_state(
        "question",
        [
            {"agent": "qa", "content": "A", "citations": [shared_citation]},
            {"agent": "portfolio", "content": "B", "citations": [shared_citation]},  # duplicate
        ],
    ))

    # Duplicate citation should appear only once
    assert len(result["final_citations"]) == 1
    assert result["final_citations"][0]["source_title"] == "Diversification Guide"


@patch("src.agents.synthesizer.get_llm")
@patch("src.agents.synthesizer.settings")
async def test_synthesizer_appends_disclaimer_when_enabled(mock_settings, mock_get_llm):
    mock_settings.guardrails_config = {"disclaimer_enabled": True}
    mock_settings.disclaimer_text = "This is not financial advice."
    mock_get_llm.return_value = MagicMock(
        ainvoke=AsyncMock(return_value=MagicMock(content="Here is a summary."))
    )

    from src.agents.synthesizer import synthesizer

    result = await synthesizer(_state(
        "question",
        [
            {"agent": "qa", "content": "A", "citations": []},
            {"agent": "tax", "content": "B", "citations": []},
        ],
    ))

    assert "This is not financial advice." in result["final_response"]


@patch("src.agents.synthesizer.get_llm")
@patch("src.agents.synthesizer.settings")
async def test_synthesizer_skips_disclaimer_if_already_present(mock_settings, mock_get_llm):
    disclaimer = "This is not financial advice."
    mock_settings.guardrails_config = {"disclaimer_enabled": True}
    mock_settings.disclaimer_text = disclaimer
    # LLM already includes disclaimer in its response
    mock_get_llm.return_value = MagicMock(
        ainvoke=AsyncMock(return_value=MagicMock(content=f"Answer. {disclaimer}"))
    )

    from src.agents.synthesizer import synthesizer

    result = await synthesizer(_state(
        "question",
        [
            {"agent": "qa", "content": "A", "citations": []},
            {"agent": "market", "content": "B", "citations": []},
        ],
    ))

    # Disclaimer should not be duplicated
    assert result["final_response"].count(disclaimer) == 1


@patch("src.agents.synthesizer.get_llm")
@patch("src.agents.synthesizer.settings")
async def test_synthesizer_merges_citations_from_all_agents(mock_settings, mock_get_llm):
    mock_settings.guardrails_config = {"disclaimer_enabled": False}
    mock_settings.disclaimer_text = ""
    mock_get_llm.return_value = MagicMock(
        ainvoke=AsyncMock(return_value=MagicMock(content="Answer."))
    )

    from src.agents.synthesizer import synthesizer

    result = await synthesizer(_state(
        "question",
        [
            {"agent": "qa", "content": "A",
             "citations": [{"source_title": "Doc 1", "source_url": "", "snippet": "..."}]},
            {"agent": "tax", "content": "B",
             "citations": [{"source_title": "Doc 2", "source_url": "", "snippet": "..."}]},
        ],
    ))

    titles = {c["source_title"] for c in result["final_citations"]}
    assert "Doc 1" in titles
    assert "Doc 2" in titles
