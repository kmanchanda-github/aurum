"""Admin observability endpoints — requires admin auth."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_admin_user, get_db
from src.core.config import settings
from src.models.chat_trace import ChatTrace
from src.models.conversation import Conversation, Message
from src.models.user import User
from src.schemas.admin import (
    AdminConversationPage,
    AdminConversationSummary,
    AdminConversationTrace,
    AdminMessageTrace,
    AdminStats,
    AdminUserPage,
    AdminUserSummary,
    ChatTraceOut,
)

router = APIRouter(prefix="/api/admin", tags=["admin"])

# Per-million-token prices in USD — update as pricing changes
_COST_PER_M: dict[str, dict[str, float]] = {
    "gpt-4o-mini":       {"input": 0.15,  "output": 0.60},
    "gpt-4o":            {"input": 2.50,  "output": 10.0},
    "gpt-4.1":           {"input": 2.00,  "output": 8.0},
    "gpt-4.1-mini":      {"input": 0.40,  "output": 1.60},
    "gpt-4-turbo":       {"input": 10.0,  "output": 30.0},
    "claude-opus-4-7":   {"input": 15.0,  "output": 75.0},
    "claude-opus-4-5":   {"input": 15.0,  "output": 75.0},
    "claude-sonnet-4-6": {"input": 3.0,   "output": 15.0},
    "claude-haiku-4-5":  {"input": 0.8,   "output": 4.0},
    "default":           {"input": 3.0,   "output": 15.0},
}


def _estimate_cost(input_tokens: int, output_tokens: int) -> float:
    prices = _COST_PER_M.get(settings.llm_model, _COST_PER_M["default"])
    return (input_tokens / 1_000_000) * prices["input"] + \
           (output_tokens / 1_000_000) * prices["output"]


@router.get("/stats", response_model=AdminStats)
async def get_stats(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_admin_user),
) -> AdminStats:
    total_users = (await db.execute(select(func.count(User.id)))).scalar_one()
    total_convs = (await db.execute(select(func.count(Conversation.id)))).scalar_one()
    total_msgs = (await db.execute(select(func.count(Message.id)))).scalar_one()

    token_row = (
        await db.execute(
            select(
                func.coalesce(func.sum(ChatTrace.total_input_tokens), 0),
                func.coalesce(func.sum(ChatTrace.total_output_tokens), 0),
            )
        )
    ).one()
    total_in, total_out = int(token_row[0]), int(token_row[1])

    langsmith_url = None
    if settings.langsmith_enabled:
        langsmith_url = f"https://smith.langchain.com/projects/{settings.langchain_project}"

    return AdminStats(
        total_users=total_users,
        total_conversations=total_convs,
        total_messages=total_msgs,
        total_input_tokens=total_in,
        total_output_tokens=total_out,
        estimated_cost_usd=_estimate_cost(total_in, total_out),
        langsmith_enabled=settings.langsmith_enabled,
        langsmith_project=settings.langchain_project if settings.langsmith_enabled else None,
        langsmith_url=langsmith_url,
    )


@router.get("/conversations", response_model=AdminConversationPage)
async def list_conversations(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    user_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_admin_user),
) -> AdminConversationPage:
    offset = (page - 1) * per_page

    # Base query for conversations + user email
    base = select(Conversation, User.email).join(User, Conversation.user_id == User.id)
    if user_id:
        base = base.where(Conversation.user_id == user_id)

    count_q = select(func.count()).select_from(
        base.subquery()
    )
    total = (await db.execute(count_q)).scalar_one()

    rows = (
        await db.execute(
            base.order_by(Conversation.created_at.desc()).offset(offset).limit(per_page)
        )
    ).all()

    items = []
    for conv, user_email in rows:
        # Get message count
        msg_count = (
            await db.execute(
                select(func.count(Message.id)).where(Message.conversation_id == conv.id)
            )
        ).scalar_one()

        # Get token totals from chat_traces
        token_row = (
            await db.execute(
                select(
                    func.coalesce(func.sum(ChatTrace.total_input_tokens), 0),
                    func.coalesce(func.sum(ChatTrace.total_output_tokens), 0),
                    func.array_agg(ChatTrace.selected_agents),
                ).where(ChatTrace.conversation_id == conv.id)
            )
        ).one()
        t_in, t_out = int(token_row[0]), int(token_row[1])

        # Flatten agents_used across all traces
        agents_set: set[str] = set()
        for agents_list in (token_row[2] or []):
            if agents_list:
                agents_set.update(agents_list)

        items.append(
            AdminConversationSummary(
                id=conv.id,
                title=conv.title,
                user_id=conv.user_id,
                user_email=user_email,
                message_count=msg_count,
                agents_used=sorted(agents_set),
                total_input_tokens=t_in,
                total_output_tokens=t_out,
                estimated_cost_usd=_estimate_cost(t_in, t_out),
                created_at=conv.created_at,
                updated_at=conv.updated_at,
            )
        )

    return AdminConversationPage(items=items, total=total, page=page, per_page=per_page)


@router.get("/conversations/{conversation_id}/trace", response_model=AdminConversationTrace)
async def get_conversation_trace(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_admin_user),
) -> AdminConversationTrace:
    conv_row = (
        await db.execute(
            select(Conversation, User.email).join(User, Conversation.user_id == User.id)
            .where(Conversation.id == conversation_id)
        )
    ).one_or_none()
    if not conv_row:
        from fastapi import HTTPException
        raise HTTPException(404, "Conversation not found")

    conv, user_email = conv_row

    messages = (
        await db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
        )
    ).scalars().all()

    msg_traces: list[AdminMessageTrace] = []
    for msg in messages:
        trace_out = None
        if msg.role == "assistant":
            ct = (
                await db.execute(
                    select(ChatTrace).where(ChatTrace.message_id == msg.id)
                )
            ).scalar_one_or_none()
            if ct:
                trace_out = ChatTraceOut.model_validate(ct)

        msg_traces.append(
            AdminMessageTrace(
                message_id=msg.id,
                role=msg.role,
                content=msg.content,
                created_at=msg.created_at,
                trace=trace_out,
            )
        )

    return AdminConversationTrace(
        conversation_id=conversation_id,
        title=conv.title,
        user_email=user_email,
        messages=msg_traces,
    )


@router.get("/users", response_model=AdminUserPage)
async def list_users(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_admin_user),
) -> AdminUserPage:
    offset = (page - 1) * per_page
    total = (await db.execute(select(func.count(User.id)))).scalar_one()

    users = (
        await db.execute(
            select(User).order_by(User.created_at.desc()).offset(offset).limit(per_page)
        )
    ).scalars().all()

    items = []
    for user in users:
        conv_count = (
            await db.execute(
                select(func.count(Conversation.id)).where(Conversation.user_id == user.id)
            )
        ).scalar_one()
        msg_count = (
            await db.execute(
                select(func.count(Message.id))
                .join(Conversation, Message.conversation_id == Conversation.id)
                .where(Conversation.user_id == user.id)
            )
        ).scalar_one()
        token_row = (
            await db.execute(
                select(
                    func.coalesce(func.sum(ChatTrace.total_input_tokens), 0),
                    func.coalesce(func.sum(ChatTrace.total_output_tokens), 0),
                ).where(ChatTrace.user_id == user.id)
            )
        ).one()
        t_in, t_out = int(token_row[0]), int(token_row[1])

        items.append(
            AdminUserSummary(
                id=user.id,
                email=user.email,
                full_name=user.full_name,
                created_at=user.created_at,
                conversation_count=conv_count,
                message_count=msg_count,
                total_input_tokens=t_in,
                total_output_tokens=t_out,
                estimated_cost_usd=_estimate_cost(t_in, t_out),
            )
        )

    return AdminUserPage(items=items, total=total, page=page, per_page=per_page)
