"""FastAPI application entry point."""
from __future__ import annotations

import uuid
from contextlib import AsyncExitStack, asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware

from src.api.limiter import limiter
from src.core.config import settings
from src.core.logging import configure_logging, get_logger

configure_logging(debug=settings.debug)
logger = get_logger(__name__)

# ── MCP Server — create http_app at module level so lifespan can be composed ──
# FastMCP 3.x requires its lifespan to be entered alongside the parent app's
# lifespan (via AsyncExitStack). Mounting alone is not enough.
_mcp_http_app = None
if settings.mcp_enabled:
    try:
        import os as _os
        from mcp_server.server import mcp as _mcp_server

        _mcp_api_key = _os.getenv("MCP_API_KEY", "")
        if _mcp_api_key:
            async def _mcp_auth(request, call_next):
                if request.headers.get("x-api-key", "") != _mcp_api_key:
                    from starlette.responses import JSONResponse
                    return JSONResponse({"error": "Unauthorized"}, status_code=401)
                return await call_next(request)
            _mcp_server.add_middleware(_mcp_auth)

        # transport="sse" for mcp-remote compatibility (Claude Desktop)
        # path="/" so SSE lives at /mcp/sse and messages at /mcp/messages
        _mcp_http_app = _mcp_server.http_app(path="/", transport="sse")
        logger.info("mcp http_app created", path="/mcp", auth=bool(_mcp_api_key))
    except Exception as _exc:
        logger.warning("mcp server not available", error=str(_exc))


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with AsyncExitStack() as stack:
        # Compose FastMCP 3.x lifespan — must be entered before startup code
        if _mcp_http_app is not None:
            await stack.enter_async_context(_mcp_http_app.lifespan(app))

        logger.info("aurum starting", provider=settings.llm_provider, model=settings.llm_model)

        # ── Database ──────────────────────────────────────────────────────────
        from src.core.database import create_all_tables
        await create_all_tables()

        # ── Demo user seed (HF Spaces / ephemeral SQLite) ─────────────────────
        # Creates a known demo account on every cold start so users don't lose
        # access after a container restart wipes the ephemeral SQLite database.
        _demo_email = "demo@aurum.ai"
        _demo_password = "AurumDemo2026!"
        try:
            from sqlalchemy import select as _select
            from src.core.database import AsyncSessionLocal as _ASL
            from src.models.user import User as _User
            from src.core.security import hash_password as _hp
            async with _ASL() as _sess:
                _exists = (await _sess.execute(
                    _select(_User).where(_User.email == _demo_email)
                )).scalar_one_or_none()
                if not _exists:
                    _sess.add(_User(
                        email=_demo_email,
                        password_hash=_hp(_demo_password),
                        full_name="Demo User",
                    ))
                    await _sess.commit()
                    logger.info("demo user seeded", email=_demo_email)
        except Exception as _e:
            logger.warning("demo user seed failed", error=str(_e))

        # ── Cache ─────────────────────────────────────────────────────────────
        from src.core.redis_client import make_cache
        app.state.cache = make_cache()

        # ── ChromaDB / RAG ────────────────────────────────────────────────────
        try:
            from src.rag.chroma_store import ChromaStore
            app.state.chroma_store = ChromaStore()

            # Auto-seed knowledge base if empty (e.g. after ephemeral restart)
            if app.state.chroma_store.count() == 0:
                logger.info("chroma empty — seeding knowledge base")
                import asyncio as _asyncio
                from src.rag.ingest import ingest as _ingest
                await _asyncio.get_event_loop().run_in_executor(
                    None, _ingest, "src/rag/seed"
                )
                logger.info("rag seeded", count=app.state.chroma_store.count())
        except Exception as exc:
            logger.warning("chroma init failed — RAG disabled", error=str(exc))
            app.state.chroma_store = None

        # ── Adapter Registry ──────────────────────────────────────────────────
        from src.adapters.registry import build_registry
        app.state.registry = build_registry(cache=app.state.cache)

        # ── LangGraph ─────────────────────────────────────────────────────────
        try:
            from src.agents.graph import build_graph
            app.state.graph = await build_graph(
                registry=app.state.registry,
                chroma_store=app.state.chroma_store,
            )
            logger.info("langgraph ready")
        except Exception as exc:
            logger.error("langgraph init failed", error=str(exc))
            app.state.graph = None

        logger.info("aurum ready")
        yield

        # ── Shutdown ──────────────────────────────────────────────────────────
        await app.state.cache.close()
        logger.info("aurum stopped")
        # AsyncExitStack cleans up MCP lifespan automatically


app = FastAPI(
    title="Aurum AI Finance Assistant",
    version="0.1.0",
    description="Multi-agent financial literacy assistant powered by LangGraph",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# ── Rate limiting ─────────────────────────────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── Request ID middleware ─────────────────────────────────────────────────────
class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

app.add_middleware(RequestIdMiddleware)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "https://*.hf.space"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Global error handler ──────────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_error(request: Request, exc: Exception) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "unknown")
    logger.error("unhandled error", path=request.url.path, error=str(exc), request_id=request_id)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "request_id": request_id},
    )

# ── Routes ────────────────────────────────────────────────────────────────────
from src.api.routes.health import router as health_router
from src.api.routes.auth import router as auth_router
from src.api.routes.chat import router as chat_router
from src.api.routes.portfolio import router as portfolio_router
from src.api.routes.market import router as market_router
from src.api.routes.goals import router as goals_router
from src.api.routes.news import router as news_router
from src.api.routes.tax import router as tax_router
from src.api.routes.settings import router as settings_router
from src.api.routes.admin import router as admin_router

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(portfolio_router)
app.include_router(market_router)
app.include_router(goals_router)
app.include_router(news_router)
app.include_router(tax_router)
app.include_router(settings_router)
app.include_router(admin_router)

# ── Mount MCP sub-app (lifespan already composed above) ──────────────────────
if _mcp_http_app is not None:
    app.mount("/mcp", _mcp_http_app, name="mcp")
    logger.info("mcp server mounted", path="/mcp")

# ── Serve React SPA (production / HF Spaces) ─────────────────────────────────
# StaticFiles serves assets. A catch-all route serves index.html for all
# unknown paths so React Router handles client-side navigation (e.g. /login,
# /dashboard) without the browser getting a 404 from FastAPI.
_ui_dist = Path("ui/dist")
if _ui_dist.exists():
    from fastapi.responses import FileResponse

    # Serve compiled assets (JS/CSS bundles) as static files
    _assets_dir = _ui_dist / "assets"
    if _assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(_assets_dir)), name="assets")

    # Catch-all: return index.html for every unknown path so React Router
    # can handle client-side routes like /login, /dashboard, /portfolio etc.
    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        """SPA fallback — serves index.html for all unmatched paths."""
        return FileResponse(str(_ui_dist / "index.html"))
