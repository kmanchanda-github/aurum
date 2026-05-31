"""Google News RSS adapter using pygooglenews (or feedparser fallback)."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from functools import partial

from src.adapters.base import NewsAdapter, NewsItem


class PyGoogleNewsAdapter(NewsAdapter):
    name = "pygooglenews"

    def __init__(self, language: str = "en", country: str = "US") -> None:
        self._lang = language
        self._country = country

    def _sync_fetch(self, query: str, limit: int) -> list[NewsItem]:
        try:
            from pygooglenews import GoogleNews
            gn = GoogleNews(lang=self._lang, country=self._country)
            feed = gn.search(query)
            entries = feed.get("entries", [])
        except Exception:
            # Fallback: direct feedparser against Google News RSS
            import feedparser
            url = (
                f"https://news.google.com/rss/search?q={query.replace(' ', '+')}"
                f"&hl={self._lang}-{self._country}&gl={self._country}&ceid={self._country}:{self._lang}"
            )
            parsed = feedparser.parse(url)
            entries = parsed.entries

        items: list[NewsItem] = []
        for entry in entries[:limit]:
            try:
                pub_str = entry.get("published", entry.get("updated", ""))
                try:
                    pub_dt = parsedate_to_datetime(pub_str).replace(tzinfo=timezone.utc)
                except Exception:
                    pub_dt = datetime.now(timezone.utc)

                source = ""
                if hasattr(entry, "source"):
                    src = entry.source
                    source = src.get("title", "") if isinstance(src, dict) else getattr(src, "title", "")

                items.append(
                    NewsItem(
                        title=entry.get("title", ""),
                        url=entry.get("link", ""),
                        source=source or "Google News",
                        published_at=pub_dt,
                        summary=entry.get("summary", "")[:300] if entry.get("summary") else None,
                    )
                )
            except Exception:
                continue
        return items

    async def fetch(
        self, query: str, since: datetime | None = None, limit: int = 10
    ) -> list[NewsItem]:
        loop = asyncio.get_event_loop()
        items = await loop.run_in_executor(None, partial(self._sync_fetch, query, limit * 2))
        if since:
            items = [i for i in items if i.published_at >= since]
        return items[:limit]
