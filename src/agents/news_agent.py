"""News synthesizer agent."""
from __future__ import annotations

from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage

from src.agents.rag import _last_user_message
from src.core.llm import get_llm
from src.core.logging import get_logger

logger = get_logger(__name__)
_PROMPT = (Path(__file__).parent / "prompts" / "news.txt").read_text()


async def news_agent(state: dict) -> dict:
    registry = state.get("__registry__")
    messages = state.get("messages", [])
    query = _last_user_message(messages)

    news_context = "News data unavailable."
    citations: list[dict] = []

    if registry:
        try:
            items = await registry.fetch_news(query=query, limit=8)
            if items:
                lines = []
                for item in items:
                    lines.append(
                        f"- **{item.title}** ({item.source}, {item.published_at.strftime('%b %d')}) "
                        f"— {item.summary or 'No summary.'}"
                    )
                    citations.append({
                        "source_title": item.title,
                        "source_url": item.url,
                        "snippet": item.summary or item.title,
                    })
                news_context = "\n".join(lines)
        except Exception as exc:
            logger.warning("news agent fetch failed", error=str(exc))

    llm = get_llm(streaming=True)
    response = await llm.ainvoke([
        SystemMessage(content=_PROMPT),
        HumanMessage(content=f"User question: {query}\n\n### Recent News\n{news_context}"),
    ])

    return {
        "agent_results": [
            {"agent": "news", "content": response.content, "citations": citations, "data": None}
        ]
    }
