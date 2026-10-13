from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.providers.base import ProviderError
from app.ai.providers.fake import FakeProvider
from app.models import AIUsage, UserRole
from tests.conftest import csrf, login_as, make_user


async def test_ai_admin_endpoints_are_admin_only(
    client: AsyncClient, db: AsyncSession, signed_in: AsyncClient
) -> None:
    assert (await client.get("/api/v1/admin/ai/providers")).status_code == 403
    assert (
        await signed_in.post("/api/v1/admin/ai/test-chat", json={}, headers=csrf(signed_in))
    ).status_code == 403


async def test_anonymous_requests_are_rejected(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/admin/ai/providers")).status_code == 401


async def test_admin_sees_which_providers_are_configured(
    client: AsyncClient, db: AsyncSession, fake_ai: FakeProvider
) -> None:
    await make_user(db, email="admin@example.com", role=UserRole.ADMIN)
    await login_as(client, "admin@example.com")

    response = await client.get("/api/v1/admin/ai/providers")

    assert response.status_code == 200
    providers = {p["name"]: p for p in response.json()}
    assert set(providers) == {"openai", "anthropic", "gemini", "fake"}
    assert providers["fake"]["active"] is True
    assert providers["fake"]["model"] == "fake-model"
    assert providers["openai"]["active"] is False
    assert providers["fake"]["healthy"] is None, "no health check unless asked"
    assert "key" not in response.text.lower(), "API keys are never returned"


async def test_health_check_reports_each_provider(
    client: AsyncClient, db: AsyncSession, fake_ai: FakeProvider
) -> None:
    await make_user(db, email="admin@example.com", role=UserRole.ADMIN)
    await login_as(client, "admin@example.com")

    response = await client.get("/api/v1/admin/ai/providers", params={"check": "true"})

    providers = {p["name"]: p for p in response.json()}
    assert providers["fake"]["healthy"] is True
    for name in ("openai", "anthropic", "gemini"):
        assert providers[name]["healthy"] is False
        assert providers[name]["detail"] == "No API key set."


async def test_test_chat_runs_end_to_end_and_is_metered(
    client: AsyncClient, db: AsyncSession, fake_ai: FakeProvider
) -> None:
    admin = await make_user(db, email="admin@example.com", role=UserRole.ADMIN)
    await login_as(client, "admin@example.com")

    response = await client.post(
        "/api/v1/admin/ai/test-chat", json={"message": "ping"}, headers=csrf(client)
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["provider"] == "fake"
    assert "ping" in body["text"]
    assert body["output_tokens"] > 0
    usage = (await db.scalars(select(AIUsage))).one()
    assert usage.user_id == admin.id


async def test_test_chat_reports_a_broken_provider_without_a_500(
    client: AsyncClient, db: AsyncSession, fake_ai: FakeProvider
) -> None:
    await make_user(db, email="admin@example.com", role=UserRole.ADMIN)
    await login_as(client, "admin@example.com")
    fake_ai.script = [ProviderError("bad key", code="auth")]

    response = await client.post("/api/v1/admin/ai/test-chat", json={}, headers=csrf(client))

    assert response.status_code == 200
    assert response.json()["ok"] is False
    assert response.json()["error"] == "auth"
