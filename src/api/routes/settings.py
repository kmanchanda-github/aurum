import time

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user, get_db
from src.models.user import User, UserSetting
from src.schemas.settings import AdapterHealth, SettingsOut, SettingsUpdate

router = APIRouter(prefix="/api/settings", tags=["settings"])


async def _get_or_create_settings(user_id: str, db: AsyncSession) -> UserSetting:
    result = await db.execute(select(UserSetting).where(UserSetting.user_id == user_id))
    setting = result.scalar_one_or_none()
    if not setting:
        setting = UserSetting(user_id=user_id)
        db.add(setting)
        await db.commit()
        await db.refresh(setting)
    return setting


@router.get("", response_model=SettingsOut)
async def get_settings(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SettingsOut:
    setting = await _get_or_create_settings(user.id, db)
    registry = request.app.state.registry
    adapter_names = registry.list_enabled()

    return SettingsOut(
        market_adapter_priority=setting.market_adapter_priority or list(adapter_names.get("market", {}).keys()),
        news_adapter_priority=setting.news_adapter_priority or list(adapter_names.get("news", {}).keys()),
        preferred_currency=setting.preferred_currency,
        watchlist=setting.watchlist or [],
    )


@router.patch("", response_model=SettingsOut)
async def update_settings(
    body: SettingsUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SettingsOut:
    setting = await _get_or_create_settings(user.id, db)
    if body.market_adapter_priority is not None:
        setting.market_adapter_priority = body.market_adapter_priority
    if body.news_adapter_priority is not None:
        setting.news_adapter_priority = body.news_adapter_priority
    if body.preferred_currency is not None:
        setting.preferred_currency = body.preferred_currency
    if body.watchlist is not None:
        setting.watchlist = body.watchlist
    await db.commit()
    return await get_settings(request, db, user)


@router.get("/adapters/health", response_model=list[AdapterHealth])
async def adapter_health(
    request: Request,
    user: User = Depends(get_current_user),
) -> list[AdapterHealth]:
    registry = request.app.state.registry
    results: list[AdapterHealth] = []

    for name, adapter in registry._market.items():
        start = time.monotonic()
        try:
            healthy = await adapter.health_check()
            latency = (time.monotonic() - start) * 1000
            results.append(AdapterHealth(name=name, enabled=True, healthy=healthy, latency_ms=latency))
        except Exception as e:
            results.append(AdapterHealth(name=name, enabled=True, healthy=False, last_error=str(e)))

    return results
