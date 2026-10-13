from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.main import create_app


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
            "database_url": base.test_database_url,
            "static_dir": static_dir,
        }
    )


@pytest.fixture(scope="session")
async def app(settings: Settings) -> AsyncIterator[FastAPI]:
    application = create_app(settings)
    async with application.router.lifespan_context(application):
        yield application


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
