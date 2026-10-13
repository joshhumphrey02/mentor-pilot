import os
import re
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# The rate limiter picks its storage when it is imported. A developer's `.env`
# may point at a real Redis; tests must count in memory, and start from zero.
os.environ["REDIS_URL"] = ""

from app.ai.providers.fake import FakeProvider
from app.core.config import Settings
from app.core.rate_limit import limiter
from app.core.security import hash_password
from app.core.time import utcnow
from app.db.base import Base
from app.main import create_app
from app.models import User, UserRole
from app.services import pathway
from app.services.email import EmailMessage

PASSWORD = "correct horse battery"


class Outbox:
    """Stands in for the SMTP sender and remembers what was sent."""

    def __init__(self) -> None:
        self.messages: list[EmailMessage] = []

    async def send(self, message: EmailMessage) -> None:
        self.messages.append(message)

    def last_to(self, address: str) -> EmailMessage:
        return next(m for m in reversed(self.messages) if m.to == address)

    def token_for(self, address: str) -> str:
        match = re.search(r"token=([\w-]+)", self.last_to(address).text)
        assert match, "no token link in the last email"
        return match.group(1)


@pytest.fixture(scope="session")
def static_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A stand-in for a Vite build, so SPA serving is tested without Node."""
    root = tmp_path_factory.mktemp("static")
    (root / "assets").mkdir()
    (root / "index.html").write_text("<!doctype html><title>Mentor Pilot</title>")
    (root / "assets" / "app-abc123.js").write_text("console.log('app')")
    (root / "manifest.webmanifest").write_text("{}")
    return root


@pytest.fixture(scope="session")
def settings(static_dir: Path) -> Settings:
    base = Settings()
    return base.model_copy(
        update={
            "environment": "test",
            "log_level": "WARNING",
            "database_url": base.test_database_url,
            "static_dir": static_dir,
            "upload_dir": static_dir.parent / "uploads",
            "public_base_url": "http://test",
            "google_client_id": "test-client-id",
            "google_client_secret": SecretStr("test-client-secret"),
            "smtp_host": None,
            # Whatever a developer's `.env` holds, tests never call a real service.
            "redis_url": None,
            "openai_api_key": None,
            "anthropic_api_key": None,
            "gemini_api_key": None,
            "youtube_api_key": None,
            # Most tests exercise the emailed-link flow, through a fake mailer.
            "email_verification": True,
            "ai_provider": "fake",
            "ai_model": "fake-model",
            "ai_fast_model": "fake-fast-model",
            "ai_task_models": {},
        }
    )


@pytest.fixture(scope="session")
async def app(settings: Settings) -> AsyncIterator[FastAPI]:
    application = create_app(settings)
    async with application.router.lifespan_context(application):
        async with application.state.engine.begin() as connection:
            await connection.run_sync(Base.metadata.drop_all)
            await connection.run_sync(Base.metadata.create_all)
        async with application.state.session_factory() as session:
            await pathway.ensure_definitions(session)
        yield application


@pytest.fixture(autouse=True)
async def _clean_state(app: FastAPI) -> AsyncIterator[None]:
    """Every test starts with empty tables and no rate-limit history."""
    limiter.enabled = False
    limiter.reset()
    yield
    # Stage definitions are reference data, loaded once for the whole run.
    tables = ", ".join(
        f'"{table.name}"'
        for table in Base.metadata.sorted_tables
        if table.name != "stage_definitions"
    )
    async with app.state.engine.begin() as connection:
        await connection.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


@pytest.fixture
def fake_ai(app: FastAPI) -> FakeProvider:
    """A fresh scripted provider installed as the app's active one."""
    provider = FakeProvider()
    app.state.ai.registry.register(provider)
    return provider


async def make_user(
    db: AsyncSession, *, email: str, role: UserRole = UserRole.STUDENT, password: str = PASSWORD
) -> User:
    """Creates a verified, onboarded account directly, skipping the email flow."""
    now = utcnow()
    user = User(
        email=email,
        full_name="Test User",
        role=role.value,
        password_hash=await hash_password(password),
        email_verified_at=now,
        privacy_accepted_at=now,
        onboarded_at=now,
        student_profile=None,
    )
    db.add(user)
    await db.commit()
    return user


async def login_as(client: AsyncClient, email: str, password: str = PASSWORD) -> None:
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text


@pytest.fixture
def outbox(app: FastAPI) -> Outbox:
    box = Outbox()
    app.state.email_sender = box
    return box


@pytest.fixture
async def db(app: FastAPI) -> AsyncIterator[AsyncSession]:
    async with app.state.session_factory() as session:
        yield session


def make_client(app: FastAPI) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with make_client(app) as c:
        yield c


def csrf(client: AsyncClient) -> dict[str, str]:
    """The header our frontend adds to every state-changing request."""
    return {"x-csrf-token": client.cookies.get("mp_csrf") or ""}


async def register_and_verify(
    client: AsyncClient, outbox: Outbox, email: str = "thandi@example.com", name: str = "Thandi M"
) -> dict[str, object]:
    """Registers, confirms the email, and leaves `client` signed in."""
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": PASSWORD, "full_name": name, "accept_privacy": True},
    )
    assert response.status_code == 202, response.text
    response = await client.post(
        "/api/v1/auth/verify-email", json={"token": outbox.token_for(email)}
    )
    assert response.status_code == 200, response.text
    body: dict[str, object] = response.json()
    return body


@pytest.fixture
async def signed_in(client: AsyncClient, outbox: Outbox) -> AsyncClient:
    await register_and_verify(client, outbox)
    return client
