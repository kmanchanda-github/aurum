"""WebSocket manager and LangGraph astream_events serializer."""
from __future__ import annotations

import json
import time
import uuid
from collections import defaultdict
from typing import Any

from fastapi import WebSocket
from langchain_core.messages import HumanMessage

from src.core.config import settings
from src.core.logging import get_logger

logger = get_logger(__name__)


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[str, list[WebSocket]] = defaultdict(list)

    async def connect(self, ws: WebSocket, conversation_id: str) -> None:
        await ws.accept()
        self._connections[conversation_id].append(ws)

    def disconnect(self, ws: WebSocket, conversation_id: str) -> None:
        sockets = self._connections.get(conversation_id, [])
        if ws in sockets:
            sockets.remove(ws)

    async def send(self, ws: WebSocket, frame: dict[str, Any]) -> None:
        try:
            await ws.send_text(json.dumps(frame))
        except Exception:
            pass


ws_manager = ConnectionManager()


def _extract_token_usage(ai_msg: Any) -> tuple[int, int]:
    """Return (input_tokens, output_tokens) from an AIMessage, provider-agnostic."""
    if hasattr(ai_msg, "usage_metadata") and ai_msg.usage_metadata:
        u = ai_msg.usage_metadata
        return u.get("input_tokens", 0), u.get("output_tokens", 0)
    rm = getattr(ai_msg, "response_metadata", {})
    u = rm.get("usage", rm.get("token_usage", {}))
    return (
        u.get("prompt_tokens", u.get("input_tokens", 0)),
        u.get("completion_tokens", u.get("output_tokens", 0)),
    )


async def stream_graph_to_ws(
    ws: WebSocket,
    graph: Any,
    user_message: str,
    conversation_id: str,
    user_id: str,
) -> dict[str, Any]:
    """
    Invoke the LangGraph graph with astream_events and forward
    each event as a typed JSON frame over the WebSocket.

    Returns the final state dict including trace_data for persistence.
    """
    message_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": conversation_id}}
    initial_state = {
        "messages": [HumanMessage(content=user_message)],
        "conversation_id": conversation_id,
        "user_id": user_id,
    }

    final_response = ""
    agents_used: list[str] = []
    citations: list[dict] = []

    # Observability accumulator
    trace_data: dict[str, Any] = {
        "intent": None,
        "routing_reason": None,
        "supervisor_confidence": None,
        "selected_agents": [],
        "rag_categories": [],
        "retrieved_docs": [],
        "agent_metrics": [],
        "_starts": {},  # run_id → {"agent": str, "t": float}
    }

    try:
        async for event in graph.astream_events(initial_state, config=config, version="v2"):
            kind = event.get("event", "")
            name = event.get("name", "")
            data = event.get("data", {})
            meta = event.get("metadata", {})
            run_id = event.get("run_id", "")
            node = meta.get("langgraph_node", name)

            # ── Agent lifecycle frames ────────────────────────────────────────
            if kind == "on_chain_start" and name.endswith("_agent"):
                agent = name.replace("_agent", "")
                agents_used.append(agent)
                trace_data["_starts"][run_id] = {"agent": node, "t": time.monotonic()}
                await ws_manager.send(ws, {"type": "agent_start", "agent": agent})

            elif kind == "on_chain_end" and name.endswith("_agent"):
                agent = name.replace("_agent", "")
                await ws_manager.send(ws, {"type": "agent_end", "agent": agent})

            # ── Track synthesizer + supervisor timing ─────────────────────────
            elif kind == "on_chain_start" and node in ("synthesizer", "supervisor_route"):
                trace_data["_starts"][run_id] = {"agent": node, "t": time.monotonic()}

            # ── Token streaming ───────────────────────────────────────────────
            elif kind == "on_chat_model_stream":
                chunk = data.get("chunk")
                if chunk and hasattr(chunk, "content") and chunk.content:
                    delta = chunk.content
                    if isinstance(delta, list):
                        delta = "".join(
                            b.get("text", "") for b in delta if isinstance(b, dict)
                        )
                    if delta:
                        final_response += delta
                        await ws_manager.send(ws, {"type": "token", "delta": delta})

            # ── LLM call complete — capture token usage ───────────────────────
            elif kind == "on_chat_model_end":
                ai_msg = data.get("output")
                if ai_msg is not None:
                    inp, out = _extract_token_usage(ai_msg)
                    # Find elapsed time via parent run or by node name
                    parent_id = event.get("parent_run_id", "")
                    start_entry = trace_data["_starts"].get(parent_id) or \
                                  trace_data["_starts"].get(run_id)
                    elapsed = int((time.monotonic() - start_entry["t"]) * 1000) \
                              if start_entry else 0
                    trace_data["agent_metrics"].append({
                        "agent": node,
                        "model": settings.llm_model,
                        "input_tokens": inp,
                        "output_tokens": out,
                        "latency_ms": elapsed,
                    })

            # ── Supervisor routing decision ───────────────────────────────────
            elif kind == "on_chain_end" and node == "supervisor_route":
                out_state = data.get("output", {})
                if isinstance(out_state, dict):
                    trace_data["intent"] = out_state.get("intent")
                    trace_data["routing_reason"] = out_state.get("routing_reason")
                    trace_data["supervisor_confidence"] = out_state.get("confidence")
                    trace_data["selected_agents"] = out_state.get("selected_agents", [])
                    trace_data["rag_categories"] = out_state.get("rag_categories", [])

            # ── RAG retrieval results ─────────────────────────────────────────
            elif kind == "on_chain_end" and node == "retrieve_rag":
                out_state = data.get("output", {})
                if isinstance(out_state, dict):
                    raw_docs = out_state.get("retrieved_docs", [])
                    trace_data["retrieved_docs"] = [
                        {
                            "source_title": d.get("source_title", "") if isinstance(d, dict)
                                            else getattr(d, "metadata", {}).get("source_title", ""),
                            "source_url": d.get("source_url", "") if isinstance(d, dict)
                                          else getattr(d, "metadata", {}).get("source_url", ""),
                            "category": d.get("category", "") if isinstance(d, dict)
                                        else getattr(d, "metadata", {}).get("category", ""),
                            "content_preview": (d.get("content", "") if isinstance(d, dict)
                                                else getattr(d, "content", ""))[:200],
                        }
                        for d in raw_docs
                    ]

            # ── Final citations ───────────────────────────────────────────────
            elif kind == "on_chain_end" and name == "persist_turn":
                output = data.get("output", {})
                if isinstance(output, dict):
                    citations = output.get("final_citations", [])
                    for c in citations:
                        await ws_manager.send(ws, {"type": "citation", **c})

    except Exception as exc:
        logger.error("graph streaming error", error=str(exc))
        await ws_manager.send(ws, {"type": "error", "message": str(exc)})
        raise

    # Compute totals for denormalized columns
    trace_data["total_input_tokens"] = sum(
        m.get("input_tokens", 0) for m in trace_data["agent_metrics"]
    )
    trace_data["total_output_tokens"] = sum(
        m.get("output_tokens", 0) for m in trace_data["agent_metrics"]
    )
    trace_data["total_latency_ms"] = sum(
        m.get("latency_ms", 0) for m in trace_data["agent_metrics"]
    )
    # Remove internal timing dict before storing
    trace_data.pop("_starts", None)

    await ws_manager.send(
        ws,
        {
            "type": "final",
            "message_id": message_id,
            "content": final_response,
            "agents_used": list(set(agents_used)),
            "citations": citations,
        },
    )

    return {
        "message_id": message_id,
        "content": final_response,
        "agents_used": list(set(agents_used)),
        "citations": citations,
        "trace_data": trace_data,
    }
