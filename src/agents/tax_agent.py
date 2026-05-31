"""Tax education agent."""
from __future__ import annotations

from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage

from src.agents.rag import format_rag_context, _last_user_message
from src.core.config import settings
from src.core.llm import get_llm
from src.core.logging import get_logger

logger = get_logger(__name__)
_PROMPT = (Path(__file__).parent / "prompts" / "tax.txt").read_text()


async def tax_agent(state: dict) -> dict:
    messages = state.get("messages", [])
    query = _last_user_message(messages)
    rag_context = format_rag_context(state.get("retrieved_docs", []))

    user_content = query
    if rag_context:
        user_content += f"\n\n{rag_context}"

    llm = get_llm(streaming=True)
    response = await llm.ainvoke([
        SystemMessage(content=_PROMPT),
        HumanMessage(content=user_content),
    ])

    # Append mandatory disclaimer to tax responses
    content = response.content
    if settings.guardrails_config.get("disclaimer_enabled", True):
        content += f"\n\n---\n*{settings.disclaimer_text}*"

    citations = [
        {"source_title": d.get("source_title", ""), "source_url": d.get("source_url", ""), "snippet": d.get("content", "")[:150]}
        for d in state.get("retrieved_docs", []) if d.get("source_title")
    ]

    return {
        "agent_results": [
            {"agent": "tax", "content": content, "citations": citations, "data": None}
        ]
    }
