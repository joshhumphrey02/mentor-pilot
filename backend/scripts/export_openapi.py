"""Writes the API's OpenAPI schema to stdout, without starting a server.

The frontend generates its typed client from this (`make api-types`), so the
TypeScript types cannot drift from the backend.
"""

import json
import sys

from app.core.config import Settings
from app.main import create_app


def main() -> None:
    # Force dev so the schema is exported even where ENVIRONMENT=prod hides it.
    app = create_app(Settings(environment="dev", log_level="WARNING"))
    json.dump(app.openapi(), sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
