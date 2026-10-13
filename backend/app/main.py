"""FastAPI app factory: mounts the versioned API and, in prod, the built SPA."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute

from app import __version__
from app.api.v1.router import api_router
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.core.middleware import RequestContextMiddleware, SecurityHeadersMiddleware
from app.core.spa import mount_spa
from app.db.session import create_engine, create_session_factory

API_PREFIX = "/api/v1"

logger = structlog.get_logger(__name__)


def _operation_id(route: APIRoute) -> str:
    # Short, stable ids ("health" not "health_api_v1_health_get") give the
    # generated TypeScript client readable names.
    return route.name


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = create_engine(settings)
        app.state.engine = engine
        app.state.session_factory = create_session_factory(engine)
        logger.info("app.started", environment=settings.environment, version=__version__)
        try:
            yield
        finally:
            await engine.dispose()

    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        lifespan=lifespan,
        generate_unique_id_function=_operation_id,
        openapi_url=None if settings.is_prod else "/api/openapi.json",
        docs_url=None if settings.is_prod else "/api/docs",
        redoc_url=None,
    )
    app.dependency_overrides[get_settings] = lambda: settings

    if settings.is_dev:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    app.add_middleware(SecurityHeadersMiddleware, settings=settings)
    # Added last so it is outermost: every response, including errors raised by
    # other middleware, carries a request id and is logged.
    app.add_middleware(RequestContextMiddleware)

    app.include_router(api_router, prefix=API_PREFIX)
    # Registered after the API so its catch-all route never shadows an endpoint.
    mount_spa(app, settings.static_dir)

    return app


app = create_app()
