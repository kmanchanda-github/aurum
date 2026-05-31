"""RAG retrieval node: fetches relevant chunks from ChromaDB before agent fan-out."""
from __future__ import annotations

from langchain_core.messages import BaseMessage

from src.core.logging import get_logger

logger = get_logger(__name__)


def _last_user_message(messages: list[BaseMessage]) -> str:
    for m in reversed(messages):
        if hasattr(m, "type") and m.type == "human":
            return m.content
    return messages[-1].content if messages else ""


async def retrieve_rag(state: dict) -> dict:
    chroma_store = state.get("__chroma_store__")
    if chroma_store is None:
        return {"retrieved_docs": []}

    messages = state.get("messages", [])
    query = _last_user_message(messages)
    categories = state.get("rag_categories", [])

    try:
        docs = chroma_store.query(query, categories=categories, k=5)
        logger.info("rag retrieved", count=len(docs), categories=categories)
        return {
            "retrieved_docs": [
                {
                    "content": d.content,
                    "source_title": d.metadata.get("source_title", ""),
                    "source_url": d.metadata.get("source_url", ""),
                    "category": d.metadata.get("category", ""),
                }
                for d in docs
            ]
        }
    except Exception as exc:
        logger.warning("rag retrieval failed", error=str(exc))
        return {"retrieved_docs": []}


def format_rag_context(retrieved_docs: list[dict]) -> str:
    if not retrieved_docs:
        return ""
    parts = ["### Knowledge Base\n"]
    for i, doc in enumerate(retrieved_docs, 1):
        title = doc.get("source_title", f"Source {i}")
        url = doc.get("source_url", "")
        ref = f"[{title}]({url})" if url else title
        parts.append(f"**{ref}**\n{doc['content']}\n")
    return "\n".join(parts)
