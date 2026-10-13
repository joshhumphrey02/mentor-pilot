# syntax=docker/dockerfile:1
# One image for the whole app: FastAPI serving the API and the built frontend.
# Note: this file has not been built during development (project rule: no
# builds). Build and smoke-test it before relying on it:
#   docker build -t mentor-pilot . && docker run --env-file .env -p 8000:8000 mentor-pilot

# --- Stage 1: build the frontend ---------------------------------------------
FROM node:24-alpine AS frontend
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
# The Vite config writes to ../backend/app/static.
RUN mkdir -p /src/backend/app/static && npm run build

# --- Stage 2: the Python runtime ---------------------------------------------
FROM python:3.12-slim AS runtime
COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /usr/local/bin/uv
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    ENVIRONMENT=prod \
    UPLOAD_DIR=/data/uploads

WORKDIR /app
# Dependencies first, so they are cached unless the lockfile changes.
COPY backend/pyproject.toml backend/uv.lock backend/.python-version ./
RUN uv sync --frozen --no-dev

COPY backend/ ./
COPY --from=frontend /src/backend/app/static ./app/static

# Run as an unprivileged user. Uploads live on a volume: local disk is not
# shared between containers, so use one container or add object storage.
RUN useradd --system --uid 10001 app && mkdir -p /data/uploads && chown -R app /data /app
USER app
VOLUME ["/data"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=4)"]

# Migrations run on start, so a deploy cannot serve code ahead of its schema.
# --proxy-headers: trust X-Forwarded-* from the load balancer in front.
CMD ["sh", "-c", "uv run --no-dev alembic upgrade head && exec uv run --no-dev uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'"]
