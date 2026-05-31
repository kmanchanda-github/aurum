import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ChatTrace(Base):
    __tablename__ = "chat_traces"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    message_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("messages.id", ondelete="CASCADE"), unique=True, index=True
    )
    conversation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    # Denormalized for fast admin aggregate queries
    user_id: Mapped[str] = mapped_column(String(36), index=True)

    # Supervisor routing decision
    intent: Mapped[str | None] = mapped_column(Text, nullable=True)
    routing_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    supervisor_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    selected_agents: Mapped[list] = mapped_column(JSON, default=list)
    rag_categories: Mapped[list] = mapped_column(JSON, default=list)

    # RAG documents retrieved
    retrieved_docs: Mapped[list] = mapped_column(JSON, default=list)

    # Per-agent LLM metrics: [{agent, model, input_tokens, output_tokens, latency_ms}]
    agent_metrics: Mapped[list] = mapped_column(JSON, default=list)

    # Denormalized totals for fast aggregation
    total_input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_latency_ms: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
