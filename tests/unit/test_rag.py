"""Unit tests for RAG layer: ChromaStore, ingest utilities."""
from __future__ import annotations

import hashlib
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ── chunk_text ────────────────────────────────────────────────────────────────


def test_chunk_text_splits_into_multiple_chunks():
    from src.rag.ingest import chunk_text

    words = " ".join([f"word{i}" for i in range(200)])
    chunks = chunk_text(words, size=50, overlap=10)
    assert len(chunks) > 1
    # Every chunk should have at most 50 words
    for chunk in chunks:
        assert len(chunk.split()) <= 50


def test_chunk_text_overlap_repeats_words():
    from src.rag.ingest import chunk_text

    words = " ".join([str(i) for i in range(100)])
    chunks = chunk_text(words, size=30, overlap=10)

    # Verify that the end of chunk N overlaps with the start of chunk N+1
    end_of_first = chunks[0].split()[-10:]
    start_of_second = chunks[1].split()[:10]
    assert end_of_first == start_of_second


def test_chunk_text_short_text_stays_single_chunk():
    from src.rag.ingest import chunk_text

    text = "short text here"
    chunks = chunk_text(text, size=800, overlap=100)
    assert len(chunks) == 1
    assert chunks[0] == text


def test_chunk_text_empty_string_returns_empty():
    from src.rag.ingest import chunk_text

    assert chunk_text("") == []


# ── parse_markdown ────────────────────────────────────────────────────────────


def test_parse_markdown_extracts_frontmatter(tmp_path: Path):
    from src.rag.ingest import parse_markdown

    md = tmp_path / "test.md"
    md.write_text(textwrap.dedent("""\
        ---
        source_title: Test Article
        category: investing
        source_url: https://example.com
        ---

        # Test Article

        This is the body content.
    """))

    text, meta = parse_markdown(md)
    assert meta["source_title"] == "Test Article"
    assert meta["category"] == "investing"
    assert meta["source_url"] == "https://example.com"
    assert "body content" in text


def test_parse_markdown_infers_category_from_directory(tmp_path: Path):
    from src.rag.ingest import parse_markdown

    category_dir = tmp_path / "tax"
    category_dir.mkdir()
    md = category_dir / "capital-gains.md"
    md.write_text("# Capital Gains\n\nSome content here.")

    _, meta = parse_markdown(md)
    assert meta["category"] == "tax"


def test_parse_markdown_infers_title_from_filename(tmp_path: Path):
    from src.rag.ingest import parse_markdown

    md = tmp_path / "dollar-cost-averaging.md"
    md.write_text("Content without frontmatter.")

    _, meta = parse_markdown(md)
    assert meta["source_title"] == "Dollar Cost Averaging"


def test_parse_markdown_no_frontmatter_returns_full_text(tmp_path: Path):
    from src.rag.ingest import parse_markdown

    md = tmp_path / "article.md"
    md.write_text("Just plain content with no frontmatter at all.")

    text, meta = parse_markdown(md)
    assert "plain content" in text
    assert "source_title" in meta


# ── ChromaStore ───────────────────────────────────────────────────────────────


def _make_chroma_store():
    """Return a ChromaStore backed by an isolated ephemeral Chroma collection."""
    import uuid
    import chromadb
    from src.rag.chroma_store import ChromaStore

    store = ChromaStore.__new__(ChromaStore)
    store._client = chromadb.EphemeralClient()
    store._col = store._client.get_or_create_collection(
        name=f"test_{uuid.uuid4().hex}",
        metadata={"hnsw:space": "cosine"},
    )
    return store


def test_chroma_store_add_and_retrieve():
    from src.rag.chroma_store import Document

    store = _make_chroma_store()
    doc = Document(
        content="Diversification reduces portfolio risk.",
        metadata={"category": "portfolio", "source_title": "Diversification Guide", "source_url": ""},
        doc_id="test-001",
    )
    store.add_documents([doc])

    results = store.query("portfolio risk", k=5)
    assert len(results) > 0
    assert any("Diversification" in r.content or "risk" in r.content for r in results)


def test_chroma_store_category_filter():
    from src.rag.chroma_store import Document

    store = _make_chroma_store()
    store.add_documents([
        Document(
            content="Compound interest grows wealth over time.",
            metadata={"category": "investing", "source_title": "Compound Interest", "source_url": ""},
            doc_id="inv-001",
        ),
        Document(
            content="Capital gains are taxed at preferential rates.",
            metadata={"category": "tax", "source_title": "Capital Gains", "source_url": ""},
            doc_id="tax-001",
        ),
    ])

    tax_results = store.query("gains tax", categories=["tax"], k=5)
    assert len(tax_results) > 0
    for r in tax_results:
        assert r.metadata.get("category") == "tax"


def test_chroma_store_empty_store_returns_empty():
    store = _make_chroma_store()
    results = store.query("anything at all", k=5)
    assert results == []


def test_chroma_store_count_reflects_documents():
    from src.rag.chroma_store import Document

    store = _make_chroma_store()
    assert store.count() == 0

    store.add_documents([
        Document(
            content="An ETF is an exchange-traded fund.",
            metadata={"category": "investing", "source_title": "ETFs", "source_url": ""},
            doc_id="etf-001",
        )
    ])
    assert store.count() == 1


def test_chroma_store_upsert_is_idempotent():
    from src.rag.chroma_store import Document

    store = _make_chroma_store()
    doc = Document(
        content="Index funds track a market index.",
        metadata={"category": "investing", "source_title": "Index Funds", "source_url": ""},
        doc_id="idx-001",
    )
    store.add_documents([doc])
    store.add_documents([doc])  # add the same doc again
    assert store.count() == 1  # should not duplicate


def test_chroma_store_multi_category_filter():
    from src.rag.chroma_store import Document

    store = _make_chroma_store()
    store.add_documents([
        Document(content="Bonds pay interest.", metadata={"category": "investing", "source_title": "Bonds", "source_url": ""}, doc_id="b1"),
        Document(content="401k is a retirement account.", metadata={"category": "tax", "source_title": "401k", "source_url": ""}, doc_id="b2"),
        Document(content="Market cycles repeat.", metadata={"category": "market", "source_title": "Cycles", "source_url": ""}, doc_id="b3"),
    ])

    results = store.query("finance", categories=["investing", "tax"], k=10)
    categories_returned = {r.metadata["category"] for r in results}
    assert "market" not in categories_returned
    assert len(categories_returned) <= 2
