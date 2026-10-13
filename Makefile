.DEFAULT_GOAL := help
.PHONY: help install dev dev-backend dev-frontend db-up db-down migrate migration seed \
        api-types test test-backend test-frontend lint typecheck format check build start

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: ## Install backend and frontend dependencies
	cd backend && uv sync
	cd frontend && npm install

dev: ## Run the API (:8000) and the Vite dev server (:5173) together
	@$(MAKE) -j2 --no-print-directory dev-backend dev-frontend

dev-backend:
	cd backend && uv run uvicorn app.main:app --reload --port 8000

dev-frontend:
	cd frontend && npm run dev

db-up: ## Start Postgres with docker compose (skip if you run Postgres locally)
	docker compose up -d --wait postgres

db-down: ## Stop the docker compose services
	docker compose down

migrate: ## Apply database migrations
	cd backend && uv run alembic upgrade head

migration: ## Autogenerate a migration: make migration m="add users"
	@test -n "$(m)" || (echo 'Usage: make migration m="describe the change"' && exit 1)
	cd backend && uv run alembic revision --autogenerate -m "$(m)"

seed: ## Load demo data
	cd backend && uv run python -m scripts.seed

api-types: ## Regenerate the frontend API types from the backend's OpenAPI schema
	cd backend && uv run python -m scripts.export_openapi > ../frontend/openapi.json
	cd frontend && npm run gen:api

test: test-backend test-frontend ## Run all tests

test-backend:
	cd backend && uv run pytest

test-frontend:
	cd frontend && npm test

lint: ## Lint both projects
	cd backend && uv run ruff check . && uv run ruff format --check .
	cd frontend && npm run lint

typecheck: ## Type-check both projects
	cd backend && uv run mypy
	cd frontend && npm run typecheck

format: ## Auto-format the backend
	cd backend && uv run ruff check --fix . && uv run ruff format .

check: lint typecheck test ## Everything CI would run

build: ## Build the frontend into backend/app/static
	cd frontend && npm run build

start: ## Serve the built app with FastAPI on :8000 (run `make build` first)
	cd backend && ENVIRONMENT=prod uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
