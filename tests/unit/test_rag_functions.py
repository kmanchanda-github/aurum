"""Unit tests for RAG retrieval node and helper functions."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage


# ── _last_user_message ────────────────────────────────────────────────────────


def test_last_user_message_returns_last_human():
    from src.agents.rag import _last_user_message

    msgs = [HumanMessage(content="first"), AIMessage(content="reply"), HumanMessage(content="second")]
    assert _last_user_message(msgs) == "second"


def test_last_user_message_single_message():
    from src.agents.rag import _last_user_message

    assert _last_user_message([HumanMessage(content="hello")]) == "hello"


def test_last_user_message_empty_list():
    from src.agents.rag import _last_user_message

    assert _last_user_message([]) == ""


def test_last_user_message_no_human_falls_back_to_last():
    from src.agents.rag import _last_user_message

    msgs = [AIMessage(content="ai only")]
    assert _last_user_message(msgs) == "ai only"


# ── format_rag_context ────────────────────────────────────────────────────────


def test_format_rag_context_empty():
    from src.agents.rag import format_rag_context

    assert format_rag_context([]) == ""


def test_format_rag_context_single_doc_no_url():
    from src.agents.rag import format_rag_context

    docs = [{"source_title": "Compound Interest", "source_url": "", "content": "Money grows."}]
    result = format_rag_context(docs)
    assert "Compound Interest" in result
    assert "Money grows." in result
    assert "Knowledge Base" in result


def test_format_rag_context_with_url():
    from src.agents.rag import format_rag_context

    docs = [{"source_title": "ETF Guide", "source_url": "https://example.com", "content": "ETFs track indices."}]
    result = format_rag_context(docs)
    assert "[ETF Guide](https://example.com)" in result


def test_format_rag_context_multiple_docs():
    from src.agents.rag import format_rag_context

    docs = [
        {"source_title": "Doc A", "source_url": "", "content": "Content A"},
        {"source_title": "Doc B", "source_url": "", "content": "Content B"},
    ]
    result = format_rag_context(docs)
    assert "Doc A" in result
    assert "Doc B" in result
    assert "Content A" in result
    assert "Content B" in result


# ── retrieve_rag node ─────────────────────────────────────────────────────────


async def test_retrieve_rag_no_store_returns_empty():
    from src.agents.rag import retrieve_rag

    state = {"messages": [HumanMessage(content="what is DCA?")], "__chroma_store__": None}
    result = await retrieve_rag(state)
    assert result["retrieved_docs"] == []


async def test_retrieve_rag_with_mock_store():
    from src.agents.rag import retrieve_rag
    from src.rag.chroma_store import Document

    mock_doc = Document(
        content="Dollar-cost averaging reduces timing risk.",
        metadata={"source_title": "DCA Guide", "source_url": "", "category": "investing"},
        doc_id="dca-001",
    )
    mock_store = MagicMock()
    mock_store.query = MagicMock(return_value=[mock_doc])

    state = {
        "messages": [HumanMessage(content="what is DCA?")],
        "__chroma_store__": mock_store,
        "rag_categories": ["investing"],
    }
    result = await retrieve_rag(state)

    assert len(result["retrieved_docs"]) == 1
    assert result["retrieved_docs"][0]["source_title"] == "DCA Guide"
    assert result["retrieved_docs"][0]["category"] == "investing"
    mock_store.query.assert_called_once_with("what is DCA?", categories=["investing"], k=5)


async def test_retrieve_rag_handles_chroma_exception():
    from src.agents.rag import retrieve_rag

    mock_store = MagicMock()
    mock_store.query = MagicMock(side_effect=RuntimeError("ChromaDB unavailable"))

    state = {
        "messages": [HumanMessage(content="test")],
        "__chroma_store__": mock_store,
        "rag_categories": [],
    }
    result = await retrieve_rag(state)
    assert result["retrieved_docs"] == []


async def test_retrieve_rag_no_categories():
    from src.agents.rag import retrieve_rag
    from src.rag.chroma_store import Document

    mock_doc = Document(
        content="Some content.", metadata={"source_title": "T", "source_url": "", "category": "tax"},
        doc_id="t1",
    )
    mock_store = MagicMock()
    mock_store.query = MagicMock(return_value=[mock_doc])

    state = {
        "messages": [HumanMessage(content="tax question")],
        "__chroma_store__": mock_store,
    }
    result = await retrieve_rag(state)
    assert len(result["retrieved_docs"]) == 1
