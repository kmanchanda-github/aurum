"""LangGraph StateGraph: supervisor → RAG → parallel agents → synthesizer → persist."""
from __future__ import annotations

from functools import partial
from typing import Any

from langchain_core.messages import BaseMessage
from langgraph.graph import END, StateGraph
from langgraph.types import Send

from src.agents.persistence import persist_turn
from src.agents.rag import retrieve_rag
from src.agents.state import FinanceStateDict
from src.agents.supervisor import supervisor_route
from src.agents.synthesizer import synthesizer
from src.core.logging import get_logger

logger = get_logger(__name__)

AGENT_MODULES = {
    "qa": "src.agents.qa_agent",
    "portfolio": "src.agents.portfolio_agent",
    "market": "src.agents.market_agent",
    "goals": "src.agents.goals_agent",
    "news": "src.agents.news_agent",
    "tax": "src.agents.tax_agent",
}


def _inject(fn, registry, chroma_store):
    """Wrap a node function to inject registry and chroma_store into state."""
    async def wrapper(state: dict) -> dict:
        enriched = dict(state)
        if registry is not None:
            enriched["__registry__"] = registry
        if chroma_store is not None:
            enriched["__chroma_store__"] = chroma_store
        return await fn(enriched)
    wrapper.__name__ = fn.__name__
    return wrapper


def _fanout_to_agents(state: dict) -> list[Send]:
    """Conditional edge: fan out to selected agents in parallel."""
    if state.get("needs_followup") and not state.get("selected_agents"):
        return [Send("clarify_node", state)]
    selected = state.get("selected_agents", ["qa"])
    return [Send(f"{agent}_agent", state) for agent in selected]


def _after_agents(state: dict) -> str:
    """After each agent finishes, route to synthesizer (if multi-agent) or persist."""
    selected = state.get("selected_agents", [])
    results = state.get("agent_results", [])
    # Route to synthesizer only when all agents have reported AND there are multiple
    if len(selected) > 1 and len(results) >= len(selected):
        return "synthesizer"
    if len(selected) <= 1 and len(results) >= 1:
        return "persist_turn"
    # Still waiting for more agents
    return "persist_turn"


async def _clarify_node(state: dict) -> dict:
    """Ask the user for clarification when supervisor confidence is low."""
    return {
        "final_response": (
            "I want to make sure I give you the most relevant information. "
            "Could you clarify what you'd like to know? For example:\n"
            "- **Portfolio analysis** (how your investments are performing)\n"
            "- **Market data** (current prices and trends)\n"
            "- **Financial education** (concepts and strategies)\n"
            "- **Goal planning** (saving for a specific target)\n"
            "- **Tax information** (account types, strategies)"
        ),
        "final_citations": [],
    }


async def build_graph(
    registry: Any = None,
    chroma_store: Any = None,
) -> Any:
    """Build and compile the LangGraph StateGraph."""
    import importlib

    g = StateGraph(FinanceStateDict)

    # Inject dependencies
    def make_rag(fn):
        return _inject(fn, registry, chroma_store)

    def make_agent(fn):
        return _inject(fn, registry, chroma_store)

    # Add nodes
    g.add_node("supervisor_route", supervisor_route)
    g.add_node("retrieve_rag", make_rag(retrieve_rag))

    for agent_name, module_path in AGENT_MODULES.items():
        mod = importlib.import_module(module_path)
        fn = getattr(mod, f"{agent_name}_agent")
        g.add_node(f"{agent_name}_agent", make_agent(fn))

    g.add_node("synthesizer", synthesizer)
    g.add_node("persist_turn", persist_turn)
    g.add_node("clarify_node", _clarify_node)

    # Edges
    g.set_entry_point("supervisor_route")
    g.add_edge("supervisor_route", "retrieve_rag")

    # RAG → fan-out to agents in parallel
    g.add_conditional_edges(
        "retrieve_rag",
        _fanout_to_agents,
        [f"{a}_agent" for a in AGENT_MODULES] + ["clarify_node"],
    )

    # Each agent → synthesizer or persist
    for agent_name in AGENT_MODULES:
        g.add_conditional_edges(
            f"{agent_name}_agent",
            _after_agents,
            {"synthesizer": "synthesizer", "persist_turn": "persist_turn"},
        )

    g.add_edge("synthesizer", "persist_turn")
    g.add_edge("persist_turn", END)
    g.add_edge("clarify_node", END)

    # Use in-memory checkpointer (swap to AsyncPostgresSaver for production)
    try:
        from langgraph.checkpoint.memory import MemorySaver
        checkpointer = MemorySaver()
    except Exception:
        checkpointer = None

    compiled = g.compile(checkpointer=checkpointer)
    logger.info("langgraph compiled", agents=list(AGENT_MODULES.keys()))
    return compiled
