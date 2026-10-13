"""Serves the built Vite app from FastAPI in production.

- `/assets/*` holds content-hashed files, so they are cached for a year.
- `index.html` (and other unhashed root files such as the service worker and
  manifest) must revalidate, otherwise clients keep running a stale app.
- Any other non-API path returns `index.html` so client-side deep links survive
  a refresh.
"""

from pathlib import Path

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import FileResponse
from starlette.responses import Response
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

IMMUTABLE = "public, max-age=31536000, immutable"
REVALIDATE = "no-cache"


class HashedAssetFiles(StaticFiles):
    async def get_response(self, path: str, scope: Scope) -> Response:
        response = await super().get_response(path, scope)
        if response.status_code == status.HTTP_200_OK:
            response.headers["Cache-Control"] = IMMUTABLE
        return response


def mount_spa(app: FastAPI, static_dir: Path) -> None:
    root = static_dir.resolve()
    index = root / "index.html"

    # check_dir=False: the directory only exists after a frontend build.
    app.mount("/assets", HashedAssetFiles(directory=root / "assets", check_dir=False), "assets")

    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str) -> FileResponse:
        if path == "api" or path.startswith("api/"):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")

        if path:
            candidate = (root / path).resolve()
            if candidate.is_relative_to(root) and candidate.is_file():
                return FileResponse(candidate, headers={"Cache-Control": REVALIDATE})
            # A missing file must 404 rather than return HTML with a 200, or
            # the browser will try to parse the app shell as an image or script.
            if Path(path).suffix:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")

        if not index.is_file():
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                "Frontend build not found. Run `make build`, or use the Vite dev server.",
            )
        return FileResponse(index, headers={"Cache-Control": REVALIDATE})
