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


async def test_the_demo_learner_has_a_project_in_progress(
    client: AsyncClient, db: AsyncSession
) -> None:
    await seed(db)
    await seed(db)
    await client.post(
        "/api/v1/auth/login",
        json={"email": "student@demo.example.com", "password": DEMO_PASSWORD},
    )

    projects = (await client.get("/api/v1/projects")).json()
    assert len(projects) == 1, "seeding twice must not duplicate the project"
    assert projects[0]["current_stage"] == "method"
    detail = (await client.get(f"/api/v1/projects/{projects[0]['id']}")).json()
    messages = (
        await client.get(f"/api/v1/conversations/{detail['latest_conversation']['id']}/messages")
    ).json()["messages"]
    assert [block["type"] for block in messages[1]["blocks"]] == [
        "markdown",
        "callout",
        "suggested_replies",
    ]
    assert len((await client.get(f"/api/v1/projects/{projects[0]['id']}/logbook")).json()) == 2
    assert len((await client.get("/api/v1/expo-events")).json()) == 1
