from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    db: str
    redis: str
    chroma: str


@router.get("/healthz", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    from sqlalchemy import text
    from src.core.database import engine
    from src.core.redis_client import get_cache

    db_ok = "ok"
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as e:
        db_ok = f"error: {e}"

    redis_ok = "ok"
    try:
        cache = get_cache()
        await cache.set("__health__", "1", ex=5)
        val = await cache.get("__health__")
        if val != "1":
            redis_ok = "error: unexpected value"
    except Exception as e:
        redis_ok = f"error: {e}"

    chroma_ok = "ok"
    try:
        chroma_store = getattr(request.app.state, "chroma_store", None)
        if chroma_store is None:
            chroma_ok = "not initialized"
    except Exception as e:
        chroma_ok = f"error: {e}"

    overall = "ok" if all(s == "ok" for s in [db_ok, redis_ok]) else "degraded"
    return HealthResponse(status=overall, db=db_ok, redis=redis_ok, chroma=chroma_ok)
