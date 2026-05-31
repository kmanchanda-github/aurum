"""LangGraph state definition for the Aurum finance assistant."""
from __future__ import annotations

from operator import add
from typing import Annotated, Any, Literal

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

AgentName = Literal["qa", "portfolio", "market", "goals", "news", "tax"]
RAGCategory = Literal["investing", "portfolio", "tax", "goals", "market"]


class AgentResult:
    def __init__(
        self,
        agent: str,
        content: str,
        citations: list[dict] | None = None,
        data: dict | None = None,
    ) -> None:
        self.agent = agent
        self.content = content
        self.citations: list[dict] = citations or []
        self.data = data

    def to_dict(self) -> dict:
        return {
            "agent": self.agent,
            "content": self.content,
            "citations": self.citations,
            "data": self.data,
        }


class FinanceState(dict):
    """
    Typed dict-like state for LangGraph.

    Required fields:
      messages             — conversation history (add_messages reducer)
      user_id              — authenticated user ID
      conversation_id      — LangGraph thread_id

    Routing fields (set by supervisor):
      intent               — detected user intent string
      selected_agents      — list of agent names to invoke
      rag_categories       — RAG categories to retrieve
      routing_reason       — supervisor's reasoning

    Data fields (filled during run):
      retrieved_docs       — RAG chunks
      tool_outputs         — arbitrary tool call results
      agent_results        — parallel-safe list (add reducer)

    Output fields:
      final_response       — synthesized response text
      final_citations      — merged citations list
      needs_followup       — whether a clarifying question was asked
      error                — error string if something went wrong
    """


# Type hints for use in node function signatures
from typing import TypedDict


class FinanceStateDict(TypedDict, total=False):
    messages: Annotated[list[BaseMessage], add_messages]
    user_id: str
    conversation_id: str
    intent: str | None
    selected_agents: list[str]
    rag_categories: list[str]
    routing_reason: str | None
    retrieved_docs: list[dict]
    tool_outputs: dict[str, Any]
    agent_results: Annotated[list[dict], add]
    final_response: str | None
    final_citations: list[dict]
    needs_followup: bool
    error: str | None
