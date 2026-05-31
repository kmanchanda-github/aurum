import numpy as np
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user, get_db
from src.models.goal import Goal
from src.models.user import User
from src.schemas.goal import GoalCreate, GoalOut, GoalUpdate, ProjectionPoint, ProjectionResponse

router = APIRouter(prefix="/api/goals", tags=["goals"])

RETURN_MAP = {"conservative": 0.05, "moderate": 0.07, "aggressive": 0.10}
VOLATILITY_MAP = {"conservative": 0.08, "moderate": 0.12, "aggressive": 0.18}


@router.get("", response_model=list[GoalOut])
async def list_goals(
    db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
) -> list[GoalOut]:
    result = await db.execute(
        select(Goal).where(Goal.user_id == user.id).order_by(Goal.priority)
    )
    return [GoalOut.model_validate(g) for g in result.scalars()]


@router.post("", response_model=GoalOut, status_code=201)
async def create_goal(
    body: GoalCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> GoalOut:
    goal = Goal(user_id=user.id, **body.model_dump())
    db.add(goal)
    await db.commit()
    await db.refresh(goal)
    return GoalOut.model_validate(goal)


@router.patch("/{goal_id}", response_model=GoalOut)
async def update_goal(
    goal_id: str,
    body: GoalUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> GoalOut:
    result = await db.execute(select(Goal).where(Goal.id == goal_id, Goal.user_id == user.id))
    goal = result.scalar_one_or_none()
    if not goal:
        raise HTTPException(404, "Goal not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(goal, field, value)
    await db.commit()
    await db.refresh(goal)
    return GoalOut.model_validate(goal)


@router.delete("/{goal_id}", status_code=204)
async def delete_goal(
    goal_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    result = await db.execute(select(Goal).where(Goal.id == goal_id, Goal.user_id == user.id))
    goal = result.scalar_one_or_none()
    if not goal:
        raise HTTPException(404, "Goal not found")
    await db.delete(goal)
    await db.commit()


@router.post("/{goal_id}/projection", response_model=ProjectionResponse)
async def project_goal(
    goal_id: str,
    years: int = 10,
    monte_carlo_runs: int = 1000,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProjectionResponse:
    result = await db.execute(select(Goal).where(Goal.id == goal_id, Goal.user_id == user.id))
    goal = result.scalar_one_or_none()
    if not goal:
        raise HTTPException(404, "Goal not found")

    annual_return = RETURN_MAP.get(goal.risk_tolerance, 0.07)
    annual_vol = VOLATILITY_MAP.get(goal.risk_tolerance, 0.12)
    monthly_return = annual_return / 12
    monthly_vol = annual_vol / (12 ** 0.5)
    months = years * 12
    contrib = float(goal.monthly_contribution)
    initial = float(goal.current_amount)
    target = float(goal.target_amount)

    rng = np.random.default_rng(42)
    all_paths = np.zeros((monte_carlo_runs, months + 1))
    all_paths[:, 0] = initial

    for month in range(1, months + 1):
        returns = rng.normal(monthly_return, monthly_vol, monte_carlo_runs)
        all_paths[:, month] = all_paths[:, month - 1] * (1 + returns) + contrib

    projection: list[ProjectionPoint] = []
    for yr in range(1, years + 1):
        month_idx = yr * 12
        values = all_paths[:, month_idx]
        projection.append(
            ProjectionPoint(
                year=yr,
                p10=float(np.percentile(values, 10)),
                p50=float(np.percentile(values, 50)),
                p90=float(np.percentile(values, 90)),
            )
        )

    final_values = all_paths[:, -1]
    prob_success = float(np.mean(final_values >= target))

    return ProjectionResponse(
        goal_id=goal_id,
        years=years,
        target_amount=target,
        projection=projection,
        probability_of_success=prob_success,
    )
