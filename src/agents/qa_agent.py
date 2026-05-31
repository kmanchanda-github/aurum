"""Finance Q&A agent: general financial education, RAG-grounded."""
from __future__ import annotations

from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage

from src.agents.rag import format_rag_context, _last_user_message
from src.core.llm import get_llm
from src.core.logging import get_logger

logger = get_logger(__name__)
_PROMPT = (Path(__file__).parent / "prompts" / "qa.txt").read_text()


async def qa_agent(state: dict) -> dict:
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

    citations = [
        {
            "source_title": d.get("source_title", ""),
            "source_url": d.get("source_url", ""),
            "snippet": d.get("content", "")[:150],
        }
        for d in state.get("retrieved_docs", [])
        if d.get("source_title")
    ]

    return {
        "agent_results": [
            {"agent": "qa", "content": response.content, "citations": citations, "data": None}
        ]
    }
