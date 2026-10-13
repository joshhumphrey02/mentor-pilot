from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from scripts.seed import DEMO_PASSWORD, seed


async def test_seeded_demo_accounts_can_log_in(client: AsyncClient, db: AsyncSession) -> None:
    """Guards against demo emails the login form would reject (reserved domains)."""
    await seed(db)

    for name in ("student", "mentor", "admin"):
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": f"{name}@demo.example.com", "password": DEMO_PASSWORD},
        )
        assert response.status_code == 200, f"{name}: {response.text}"
        client.cookies.clear()


async def test_seeding_twice_changes_nothing(db: AsyncSession) -> None:
    from sqlalchemy import func, select

    from app.models import School, User

    await seed(db)
    await seed(db)

    assert await db.scalar(select(func.count()).select_from(User)) == 3
    assert await db.scalar(select(func.count()).select_from(School)) == 3
