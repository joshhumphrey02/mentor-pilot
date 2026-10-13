# Mentor Pilot

An AI STEM project mentor that takes learners from "I want to do a science fair
project" to a project that is researched, designed, tested and ready for the
expo, then hands them to a human mentor when it is time to build.

The full product brief and build plan is in [mentor-pilot-prompt.md](mentor-pilot-prompt.md).
Judgement calls are recorded in [DECISIONS.md](DECISIONS.md).

## Stack

- **Backend:** Python 3.12, FastAPI, SQLAlchemy 2 (async) + asyncpg, Alembic, structlog. Managed with [uv](https://docs.astral.sh/uv/).
- **Frontend:** Vite, React 19, TypeScript (strict), Tailwind CSS v4, shadcn/ui, TanStack Router and Query, Zustand.
- **Database:** PostgreSQL. Redis is optional.

In production FastAPI serves the built frontend, so the whole app is one service.

## Setup

You need [uv](https://docs.astral.sh/uv/), Node 22+ and PostgreSQL.

```sh
make install
```

### Database setup

Either start Postgres with Docker:

```sh
make db-up
```

or, if Postgres already runs on your machine, create the role and databases once:

```sh
psql -d postgres -c "CREATE ROLE mentor LOGIN PASSWORD 'mentor'" \
  -c "CREATE DATABASE mentor_pilot OWNER mentor" \
  -c "CREATE DATABASE mentor_pilot_test OWNER mentor"
```

Then apply migrations:

```sh
make migrate
```

Load the demo accounts (optional):

```sh
make seed
```

| Role | Email | Password |
| --- | --- | --- |
| Learner | `student@mentorpilot.test` | `mentorpilot-demo` |
| Mentor | `mentor@mentorpilot.test` | `mentorpilot-demo` |
| Admin | `admin@mentorpilot.test` | `mentorpilot-demo` |

Configuration is optional in dev. To change anything, copy `.env.example` to
`.env`; every variable is documented there.

## Running

```sh
make dev
```

- App: http://localhost:5173 (Vite, with `/api` proxied to the backend)
- API docs: http://localhost:8000/api/docs
- Health: http://localhost:8000/api/v1/health

**Emails in dev** are not sent: they are printed in the backend's terminal
output. When you register, copy the confirmation link from there. To send real
email, set the `SMTP_*` variables.

**Sign in with Google** appears once `GOOGLE_CLIENT_ID` and
`GOOGLE_CLIENT_SECRET` are set (see `.env.example` for the redirect URI).

To run it the way production does (FastAPI serving the built frontend):

```sh
make build
make start     # http://localhost:8000
```

## Everyday commands

Run `make help` for the full list.

| Command | What it does |
| --- | --- |
| `make dev` | API and frontend dev servers together |
| `make test` | Backend (pytest) and frontend (Vitest) tests |
| `make lint` / `make typecheck` | ruff + oxlint / mypy + tsc |
| `make check` | Lint, type-check and test everything |
| `make migration m="..."` | Autogenerate an Alembic migration |
| `make migrate` | Apply migrations |
| `make api-types` | Regenerate frontend API types after changing the API |

## Project structure

```
backend/
  app/
    main.py        FastAPI app factory: mounts the API and the built SPA
    core/          settings, security, CSRF, rate limits, logging, SPA serving
    db/            engine, session, declarative base
    api/v1/        thin routers (auth, users, schools, health)
    services/      business logic (auth, sessions, email, onboarding)
    models/ schemas/ ai/
    static/        Vite build output (git-ignored)
  alembic/         migrations
  scripts/         seed and OpenAPI export
  tests/
frontend/
  src/
    routes/        file-based routes (TanStack Router)
    components/ui/ shadcn components
    features/      feature modules
    lib/api/       typed API client generated from the OpenAPI schema
    stores/        Zustand stores
    index.css      design tokens (light and dark)
```
