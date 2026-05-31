import json

from fastapi import APIRouter, Depends, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user, get_db
from src.api.ws import stream_graph_to_sse, stream_graph_to_ws, ws_manager
from src.core.security import decode_token
from src.models.conversation import Conversation, Message
from src.models.user import User
from src.schemas.chat import ConversationCreate, ConversationOut, MessageOut

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/conversations", response_model=ConversationOut, status_code=201)
async def create_conversation(
    body: ConversationCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ConversationOut:
    conv = Conversation(user_id=user.id, title=body.title)
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return ConversationOut.model_validate(conv)


@router.get("/conversations", response_model=list[ConversationOut])
async def list_conversations(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ConversationOut]:
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == user.id)
        .order_by(Conversation.updated_at.desc())
        .limit(50)
    )
    return [ConversationOut.model_validate(c) for c in result.scalars()]


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageOut])
async def get_messages(
    conversation_id: str,
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[MessageOut]:
    conv_result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id, Conversation.user_id == user.id
        )
    )
    if not conv_result.scalar_one_or_none():
        raise HTTPException(404, "Conversation not found")

    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
        .limit(limit)
    )
    return [MessageOut.model_validate(m) for m in result.scalars()]


@router.delete("/conversations/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id, Conversation.user_id == user.id
        )
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(404, "Conversation not found")
    await db.delete(conv)
    await db.commit()


@router.post("/stream")
async def chat_stream(
    request: Request,
    conversation_id: str = Query(...),
    user: User = Depends(get_current_user),
) -> StreamingResponse:
    """SSE streaming endpoint — proxy-compatible alternative to WebSocket.

    POST body: {"content": "user message"}
    Response:  text/event-stream — same frame types as the WebSocket endpoint
               (agent_start, token, citation, final, error).
    """
    body = await request.json()
    content = (body.get("content") or "").strip()
    if not content:
        raise HTTPException(400, "Empty message")

    graph = request.app.state.graph
    if graph is None:
        raise HTTPException(503, "AI service unavailable — graph not initialized")

    from src.core.database import AsyncSessionLocal
    from src.models.chat_trace import ChatTrace

    async def event_stream():
        # ── Persist user message ──────────────────────────────────────────────
        async with AsyncSessionLocal() as sess:
            conv = (
                await sess.execute(
                    select(Conversation).where(
                        Conversation.id == conversation_id,
                        Conversation.user_id == user.id,
                    )
                )
            ).scalar_one_or_none()
            if not conv:
                conv = Conversation(
                    id=conversation_id, user_id=user.id, title=content[:60]
                )
                sess.add(conv)
            elif conv.title in ("New Conversation", "", None):
                # First real message — replace the placeholder title
                conv.title = content[:60] + ("…" if len(content) > 60 else "")
            sess.add(
                Message(
                    conversation_id=conversation_id, role="user", content=content
                )
            )
            await sess.commit()

        # ── Stream LangGraph events ───────────────────────────────────────────
        final_event: dict = {}
        async for chunk in stream_graph_to_sse(
            graph, content, conversation_id, str(user.id)
        ):
            yield chunk
            if chunk.startswith("data: "):
                try:
                    ev = json.loads(chunk[6:])
                    if ev.get("type") == "final":
                        final_event = ev
                except Exception:
                    pass

        # ── Persist assistant message + trace ─────────────────────────────────
        if final_event:
            async with AsyncSessionLocal() as sess:
                asst = Message(
                    conversation_id=conversation_id,
                    role="assistant",
                    content=final_event.get("content", ""),
                    agents_used=final_event.get("agents_used", []),
                    citations=final_event.get("citations", []),
                )
                sess.add(asst)
                await sess.flush()

                trace = final_event.get("trace_data", {})
                if trace:
                    sess.add(
                        ChatTrace(
                            message_id=asst.id,
                            conversation_id=conversation_id,
                            user_id=str(user.id),
                            intent=trace.get("intent"),
                            routing_reason=trace.get("routing_reason"),
                            supervisor_confidence=trace.get("supervisor_confidence"),
                            selected_agents=trace.get("selected_agents", []),
                            rag_categories=trace.get("rag_categories", []),
                            retrieved_docs=trace.get("retrieved_docs", []),
                            agent_metrics=trace.get("agent_metrics", []),
                            total_input_tokens=trace.get("total_input_tokens", 0),
                            total_output_tokens=trace.get("total_output_tokens", 0),
                            total_latency_ms=trace.get("total_latency_ms", 0),
                        )
                    )
                await sess.commit()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable nginx / HF proxy buffering
            "Connection": "keep-alive",
        },
    )


@router.websocket("/ws")
async def chat_ws(
    websocket: WebSocket,
    conversation_id: str = Query(...),
    token: str = Query(...),
) -> None:
    """
    WebSocket endpoint for streaming chat.
    Query params: ?conversation_id=...&token=<jwt>
    Receives: JSON {"content": "user message"}
    Sends: typed frames (agent_start, token, citation, final, error)
    """
    # Auth via query param token
    try:
        payload = decode_token(token)
        user_id = payload["sub"]
    except (ValueError, KeyError):
        await websocket.close(code=4001)
        return

    await ws_manager.connect(websocket, conversation_id)
    graph = websocket.app.state.graph

    try:
        # Save user message to DB before streaming
        from src.core.database import AsyncSessionLocal

        while True:
            raw = await websocket.receive_text()
            data = json.loads(raw)
            user_content = data.get("content", "")
            if not user_content.strip():
                continue

            async with AsyncSessionLocal() as db:
                # Ensure conversation exists for this user
                result = await db.execute(
                    select(Conversation).where(
                        Conversation.id == conversation_id,
                        Conversation.user_id == user_id,
                    )
                )
                conv = result.scalar_one_or_none()
                if not conv:
                    conv = Conversation(
                        id=conversation_id, user_id=user_id, title=user_content[:80]
                    )
                    db.add(conv)

                user_msg = Message(
                    conversation_id=conversation_id,
                    role="user",
                    content=user_content,
                )
                db.add(user_msg)
                await db.commit()

            # Stream through LangGraph
            result = await stream_graph_to_ws(
                websocket, graph, user_content, conversation_id, user_id
            )

            # Persist assistant response + observability trace
            async with AsyncSessionLocal() as db:
                asst_msg = Message(
                    conversation_id=conversation_id,
                    role="assistant",
                    content=result["content"],
                    agents_used=result["agents_used"],
                    citations=result["citations"],
                )
                db.add(asst_msg)
                await db.flush()  # get asst_msg.id before commit

                trace = result.get("trace_data", {})
                if trace:
                    from src.models.chat_trace import ChatTrace
                    ct = ChatTrace(
                        message_id=asst_msg.id,
                        conversation_id=conversation_id,
                        user_id=user_id,
                        intent=trace.get("intent"),
                        routing_reason=trace.get("routing_reason"),
                        supervisor_confidence=trace.get("supervisor_confidence"),
                        selected_agents=trace.get("selected_agents", []),
                        rag_categories=trace.get("rag_categories", []),
                        retrieved_docs=trace.get("retrieved_docs", []),
                        agent_metrics=trace.get("agent_metrics", []),
                        total_input_tokens=trace.get("total_input_tokens", 0),
                        total_output_tokens=trace.get("total_output_tokens", 0),
                        total_latency_ms=trace.get("total_latency_ms", 0),
                    )
                    db.add(ct)

                await db.commit()

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        from src.core.logging import get_logger
        get_logger(__name__).error("ws error", error=str(exc))
    finally:
        ws_manager.disconnect(websocket, conversation_id)
