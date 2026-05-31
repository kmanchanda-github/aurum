#!/usr/bin/env python3
"""
Seed demo data: creates a demo user with a sample portfolio and goals.

Usage:
    python scripts/seed_demo_data.py

Requires the API to be running (or DATABASE_URL configured in .env).
"""
import asyncio
import os
import sys

# Allow running from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("USE_SQLITE", "false")

from decimal import Decimal
from datetime import date, timedelta

from sqlalchemy import select


DEMO_EMAIL = "demo@aurum.app"
DEMO_PASSWORD = "DemoPass123!"


async def main():
    from src.core.database import AsyncSessionLocal, create_all_tables
    from src.core.security import create_access_token, hash_password
    from src.models.user import User, UserSetting
    from src.models.portfolio import Holding, Portfolio
    from src.models.goal import Goal

    await create_all_tables()

    async with AsyncSessionLocal() as db:
        # Check if demo user already exists
        result = await db.execute(select(User).where(User.email == DEMO_EMAIL))
        user = result.scalar_one_or_none()

        if not user:
            user = User(
                email=DEMO_EMAIL,
                password_hash=hash_password(DEMO_PASSWORD),
                full_name="Demo User",
                risk_tolerance="moderate",
                knowledge_level="intermediate",
            )
            db.add(user)
            await db.flush()

            setting = UserSetting(user_id=user.id, market_adapter_priority=[], news_adapter_priority=[])
            db.add(setting)
            print(f"Created demo user: {DEMO_EMAIL} / {DEMO_PASSWORD}")
        else:
            print(f"Demo user already exists: {DEMO_EMAIL}")

        # Portfolio
        result = await db.execute(
            select(Portfolio).where(Portfolio.user_id == user.id, Portfolio.name == "My Portfolio")
        )
        portfolio = result.scalar_one_or_none()

        if not portfolio:
            portfolio = Portfolio(user_id=user.id, name="My Portfolio")
            db.add(portfolio)
            await db.flush()

            holdings = [
                Holding(portfolio_id=portfolio.id, symbol="AAPL", quantity=Decimal("25"),
                        cost_basis=Decimal("3750.00"), asset_class="stock",
                        purchase_date=date.today() - timedelta(days=365)),
                Holding(portfolio_id=portfolio.id, symbol="MSFT", quantity=Decimal("15"),
                        cost_basis=Decimal("4500.00"), asset_class="stock",
                        purchase_date=date.today() - timedelta(days=300)),
                Holding(portfolio_id=portfolio.id, symbol="VTI", quantity=Decimal("50"),
                        cost_basis=Decimal("10000.00"), asset_class="etf",
                        purchase_date=date.today() - timedelta(days=500)),
                Holding(portfolio_id=portfolio.id, symbol="BND", quantity=Decimal("30"),
                        cost_basis=Decimal("2400.00"), asset_class="bond",
                        purchase_date=date.today() - timedelta(days=200)),
            ]
            db.add_all(holdings)
            print(f"Created demo portfolio with {len(holdings)} holdings")

        # Goals
        result = await db.execute(select(Goal).where(Goal.user_id == user.id))
        goals = result.scalars().all()

        if not goals:
            demo_goals = [
                Goal(
                    user_id=user.id,
                    name="Retirement Fund",
                    target_amount=Decimal("2000000"),
                    current_amount=Decimal("85000"),
                    monthly_contribution=Decimal("2000"),
                    target_date=date.today().replace(year=date.today().year + 25),
                    risk_tolerance="moderate",
                    priority=1,
                ),
                Goal(
                    user_id=user.id,
                    name="House Down Payment",
                    target_amount=Decimal("100000"),
                    current_amount=Decimal("35000"),
                    monthly_contribution=Decimal("1500"),
                    target_date=date.today() + timedelta(days=365 * 3),
                    risk_tolerance="conservative",
                    priority=2,
                ),
            ]
            db.add_all(demo_goals)
            print(f"Created {len(demo_goals)} demo goals")

        await db.commit()

    token = create_access_token(subject=user.id)
    print(f"\nDemo login token (valid 7 days):\n{token}")
    print("\nDone! Start the app and log in with:")
    print(f"  Email:    {DEMO_EMAIL}")
    print(f"  Password: {DEMO_PASSWORD}")


if __name__ == "__main__":
    asyncio.run(main())
