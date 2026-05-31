"""Synthesizer node: merges multi-agent results into one coherent response."""
from __future__ import annotations

from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage

from src.agents.rag import _last_user_message
from src.core.config import settings
from src.core.llm import get_llm
from src.core.logging import get_logger

logger = get_logger(__name__)
_PROMPT = (Path(__file__).parent / "prompts" / "synthesizer.txt").read_text()


async def synthesizer(state: dict) -> dict:
    agent_results: list[dict] = state.get("agent_results", [])
    messages = state.get("messages", [])
    query = _last_user_message(messages)

    if len(agent_results) == 1:
        # Pass-through — no synthesis needed
        result = agent_results[0]
        return {
            "final_response": result["content"],
            "final_citations": result.get("citations", []),
        }

    # Build combined context for synthesis
    agent_sections = []
    all_citations: list[dict] = []
    seen_citations: set[str] = set()

    for result in agent_results:
        agent = result.get("agent", "")
        content = result.get("content", "")
        agent_sections.append(f"### {agent.upper()} AGENT RESPONSE\n{content}")
        for c in result.get("citations", []):
            key = c.get("source_title", "")
            if key and key not in seen_citations:
                seen_citations.add(key)
                all_citations.append(c)

    combined = f"Original question: {query}\n\n" + "\n\n".join(agent_sections)

    llm = get_llm(streaming=True)
    response = await llm.ainvoke([
        SystemMessage(content=_PROMPT),
        HumanMessage(content=combined),
    ])

    content = response.content
    if settings.guardrails_config.get("disclaimer_enabled", True):
        if settings.disclaimer_text not in content:
            content += f"\n\n---\n*{settings.disclaimer_text}*"

    return {
        "final_response": content,
        "final_citations": all_citations,
    }
