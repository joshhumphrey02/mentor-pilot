"""Seeds demo data for local development. Run with `make seed`."""

import structlog

from app.core.config import get_settings
from app.core.logging import configure_logging

logger = structlog.get_logger(__name__)


def main() -> None:
    configure_logging(get_settings())
    # Seed data arrives with the models: users and schools in Phase 2, stage
    # definitions and a demo project in Phase 5.
    logger.info("seed.nothing_to_seed_yet")


if __name__ == "__main__":
    main()
