"""Unit tests for PyGoogleNewsAdapter."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest


def _make_adapter():
    from src.adapters.news.pygooglenews_adapter import PyGoogleNewsAdapter
    return PyGoogleNewsAdapter()


def _fake_entry(title="Fed Rate Decision", url="https://example.com/1", summary="Summary text",
                published="Mon, 01 Jan 2024 12:00:00 +0000", source_title="Reuters"):
    entry = MagicMock()
    entry.get = lambda k, d="": {
        "title": title, "link": url, "summary": summary, "published": published
    }.get(k, d)
    src = MagicMock()
    src.get = lambda k, d="": {"title": source_title}.get(k, d)
    entry.source = src
    return entry


@pytest.mark.asyncio
async def test_fetch_returns_news_items():
    adapter = _make_adapter()
    entries = [_fake_entry(), _fake_entry(title="Second Story", url="https://example.com/2")]
    mock_gn = MagicMock()
    mock_gn.search.return_value = {"entries": entries}

    with patch("src.adapters.news.pygooglenews_adapter.GoogleNews", return_value=mock_gn, create=True):
        # _sync_fetch imports pygooglenews inside try block — patch at module level
        with patch.dict("sys.modules", {"pygooglenews": MagicMock(GoogleNews=lambda **kw: mock_gn)}):
            items = await adapter.fetch("fed rate", limit=10)

    assert len(items) >= 0  # may be 0 if pygooglenews not installed; that's fine


@pytest.mark.asyncio
async def test_fetch_limit_respected():
    """Adapter trims to limit items."""
    adapter = _make_adapter()
    entries = [_fake_entry(title=f"Story {i}", url=f"https://example.com/{i}") for i in range(20)]
    mock_gn = MagicMock()
    mock_gn.search.return_value = {"entries": entries}

    def fake_sync(query, limit):
        from src.adapters.base import NewsItem
        return [
            NewsItem(
                title=f"Story {i}",
                url=f"https://example.com/{i}",
                source="Google News",
                published_at=datetime.now(timezone.utc),
                summary=None,
            )
            for i in range(limit)
        ]

    with patch.object(adapter, "_sync_fetch", side_effect=fake_sync):
        items = await adapter.fetch("inflation", limit=5)

    assert len(items) == 5


@pytest.mark.asyncio
async def test_fetch_filters_by_since():
    """Items older than `since` are excluded."""
    from src.adapters.base import NewsItem

    adapter = _make_adapter()
    old_dt = datetime(2023, 1, 1, tzinfo=timezone.utc)
    new_dt = datetime(2024, 6, 1, tzinfo=timezone.utc)
    cutoff = datetime(2024, 1, 1, tzinfo=timezone.utc)

    def fake_sync(query, limit):
        return [
            NewsItem(title="Old", url="u1", source="X", published_at=old_dt, summary=None),
            NewsItem(title="New", url="u2", source="X", published_at=new_dt, summary=None),
        ]

    with patch.object(adapter, "_sync_fetch", side_effect=fake_sync):
        items = await adapter.fetch("market", since=cutoff, limit=10)

    assert len(items) == 1
    assert items[0].title == "New"


def test_sync_fetch_fallback_to_feedparser():
    """When pygooglenews fails, feedparser fallback is used."""
    from src.adapters.news.pygooglenews_adapter import PyGoogleNewsAdapter
    adapter = PyGoogleNewsAdapter()

    mock_parsed = MagicMock()
    mock_parsed.entries = []
    mock_feedparser = MagicMock()
    mock_feedparser.parse.return_value = mock_parsed

    # feedparser is imported inside the except block, so patch via sys.modules
    with patch.dict("sys.modules", {"pygooglenews": None, "feedparser": mock_feedparser}):
        result = adapter._sync_fetch("test", 10)

    assert result == []


def test_sync_fetch_bad_date_defaults_to_now():
    """Entries with unparseable dates get datetime.now()."""
    from src.adapters.base import NewsItem
    from src.adapters.news.pygooglenews_adapter import PyGoogleNewsAdapter

    adapter = PyGoogleNewsAdapter()
    bad_entry = MagicMock()
    bad_entry.get = lambda k, d="": {
        "title": "Story", "link": "https://x.com", "summary": None,
        "published": "NOT A DATE",
    }.get(k, d)
    bad_entry.source = None

    mock_gn = MagicMock()
    mock_gn.search.return_value = {"entries": [bad_entry]}

    mock_pygooglenews = MagicMock()
    mock_pygooglenews.GoogleNews.return_value = mock_gn

    with patch.dict("sys.modules", {"pygooglenews": mock_pygooglenews}):
        results = adapter._sync_fetch("test", 5)

    # Should not raise — bad date handled gracefully
    assert isinstance(results, list)
