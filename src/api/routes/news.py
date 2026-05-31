from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel

from src.api.deps import get_current_user
from src.models.user import User

router = APIRouter(prefix="/api/news", tags=["news"])


class NewsItemOut(BaseModel):
    title: str
    url: str
    source: str
    published_at: datetime
    summary: str | None = None


@router.get("", response_model=list[NewsItemOut])
async def get_news(
    query: str = Query("financial markets investing"),
    limit: int = Query(10, le=30),
    request: Request = None,
    user: User = Depends(get_current_user),
) -> list[NewsItemOut]:
    registry = request.app.state.registry
    items = await registry.fetch_news(query=query, limit=limit)
    return [
        NewsItemOut(
            title=item.title,
            url=item.url,
            source=item.source,
            published_at=item.published_at,
            summary=item.summary,
        )
        for item in items
    ]
