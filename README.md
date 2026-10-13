# Mentor Pilot

An AI STEM project mentor that takes learners from "I want to do a science fair
project" to a project that is researched, designed, tested and ready for the
expo, then hands them to a human mentor when it is time to build.

- The product brief and build plan: [mentor-pilot-prompt.md](mentor-pilot-prompt.md)
- Judgement calls and known gaps, phase by phase: [DECISIONS.md](DECISIONS.md)

## What it does

- **A structured mentor, not a chat box.** Every project moves through nine
  stages, each with a goal, a checklist and exit criteria. The mentor always
  knows the stage and what comes next.
- **It shows rather than tells.** Replies are made of typed visual blocks: idea
  cards, diagrams, charts, photos, materials lists, quizzes and an interactive
  breadboard with reveal-inside, Do/Don't and step-through.
- **It protects the learner's thinking.** It asks, offers options and gives
  feedback. It does not write the project.
- **It is safe for minors.** Messages are moderated in both directions, unsafe
  experiments are redirected, and human mentors are vetted before they see any
  learner.
- **It connects to real people.** Learners can request a human mentor for
  hands-on help and message them inside the app.

## Stack

- **Backend:** Python 3.12, FastAPI, SQLAlchemy 2 (async) + asyncpg, Alembic,
  structlog, tenacity. Managed with [uv](https://docs.astral.sh/uv/).
- **Frontend:** Vite, React 19, TypeScript (strict), Tailwind CSS v4, shadcn/ui,
  TanStack Router and Query, Zustand. Installable as a PWA.
- **AI:** OpenAI, Anthropic or Gemini behind one interface, chosen by an
  environment variable.
- **Database:** PostgreSQL. Redis is optional (shared rate limits).

In production FastAPI serves the built frontend, so the whole app is one service.

## Setup

You need [uv](https://docs.astral.sh/uv/), Node 22+ and PostgreSQL.

```sh
make install
```

### Database

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

Then:

```sh
make migrate   # create the tables
make seed      # demo accounts, a demo project and an expo date (optional)
```

| Role | Email | Password |
| --- | --- | --- |
| Learner | `student@demo.example.com` | `mentorpilot-demo` |
| Mentor | `mentor@demo.example.com` | `mentorpilot-demo` |
| Admin | `admin@demo.example.com` | `mentorpilot-demo` |

Configuration is optional in dev. To change anything, copy `.env.example` to
`.env`; every variable is documented there.

## Running

```sh
make dev
```

- App: http://localhost:5173 (Vite, with `/api` proxied to the backend)
- API docs: http://localhost:8000/api/docs

**No AI key yet?** Run with the built-in demo provider:

```sh
AI_PROVIDER=fake AI_MODEL=fake make dev
```

Then log in as the demo learner and ask *"How do I connect an LED on a
breadboard?"* to see the interactive breadboard.

**Emails in dev** are not sent: they are printed in the backend's terminal
output. When you register, copy the confirmation link from there. To send real
email, set the `SMTP_*` variables.

**Sign in with Google** appears once `GOOGLE_CLIENT_ID` and
`GOOGLE_CLIENT_SECRET` are set (see `.env.example` for the redirect URI).

## The AI mentor

The app talks to AI through one provider-neutral layer (`backend/app/ai`).
Nothing outside `ai/providers/` imports a vendor SDK.

**Switching provider** is configuration only:

```sh
AI_PROVIDER=gemini          # openai | anthropic | gemini | fake
AI_MODEL=<that vendor's model id>
AI_FAST_MODEL=<a cheaper model for titles and summaries>
GEMINI_API_KEY=...
```

Restart the backend, then confirm it works. Log in as the admin and open
**Admin → AI**, or call:

```sh
GET  /api/v1/admin/ai/providers?check=true   # which keys are set, and do they work
POST /api/v1/admin/ai/test-chat              # one message through the active provider
```

or run the live tests, which are skipped unless a key is set:

```sh
cd backend && AI_PROVIDER=gemini AI_MODEL=... GEMINI_API_KEY=... uv run pytest tests/ai/test_live.py
```

**The pathway.** The nine stages, with their goals, checklists, exit criteria
and mentoring instructions, are data: they ship in
`backend/app/pathway/stages.yaml`, are loaded into the database on first start,
and are edited from **Admin → Stages** after that.

**Tools.** The mentor shows visual blocks by calling tools in
`backend/app/ai/tools`. Photo search (Wikimedia Commons) needs no key. Video
search is offered only when `YOUTUBE_API_KEY` is set.

**The breadboard.** Every circuit is checked electrically on the server before
it is shown (`backend/app/ai/circuits.py`). To add a component, add it to
`COMPONENTS` there and to `frontend/src/features/circuit/library.tsx`.

**Cost tracking.** Every AI call is written to `ai_usage` with its tokens and
an estimated cost from `backend/app/ai/pricing.yaml`. Only Anthropic prices
are filled in; add the models you run. **Admin → Usage** reports by day, user,
school or model.

## Tests and checks

| Command | What it does |
| --- | --- |
| `make test` | Backend (pytest, against the test database) and frontend (Vitest) |
| `make e2e` | The learner journey in a real browser at 390x844 (Playwright) |
| `make lint` / `make typecheck` | ruff + oxlint / mypy (strict) + tsc (strict) |
| `make check` | Lint, type-check and test everything |

`make e2e` starts both servers with the demo AI provider. Before the first run:
`make seed` and `cd frontend && npx playwright install chromium`.

Other everyday commands (`make help` lists them all):

| Command | What it does |
| --- | --- |
| `make migration m="..."` | Autogenerate an Alembic migration |
| `make api-types` | Regenerate the frontend's API types after changing the API |

## Building and deploying

```sh
make build     # builds the frontend into backend/app/static
make start     # serves everything with FastAPI on :8000, in prod mode
```

Or as a container (see the notes at the top of the `Dockerfile`):

```sh
docker build -t mentor-pilot .
docker run --env-file .env -p 8000:8000 -v mentor-pilot-data:/data mentor-pilot
```

In production you must set, at minimum:

- `ENVIRONMENT=prod`
- `SECRET_KEY` to a long random value (the app refuses to start without it)
- `DATABASE_URL`
- `PUBLIC_BASE_URL` to your real https origin
- `AI_PROVIDER`, `AI_MODEL` and that provider's API key
- `SMTP_*`, or no email (verification, password reset) will be sent

and should set `REDIS_URL` if you run more than one worker.

Before a real launch, read the "not verified" and "needs review" notes in
[DECISIONS.md](DECISIONS.md): among them, the production build, Docker image
and Lighthouse score have not been run, live AI providers have not been
called, uploads use local disk, and the privacy notice needs legal review.

## Project structure

```
backend/
  app/
    main.py        FastAPI app factory: mounts the API and the built SPA
    core/          settings, security, CSRF, rate limits, logging, SPA serving
    db/            engine, session, declarative base
    api/v1/        thin routers
    services/      business logic (auth, chat turns, pathway, mentoring, ...)
    ai/            provider-neutral AI layer
      providers/   openai, anthropic, gemini, fake
      tools/       the mentor's tools
      prompts/     the layered system prompt
      blocks.py    render-block schemas (the source of the frontend's types)
      circuits.py  breadboard model and wiring checks
    pathway/       the nine stages (stages.yaml)
    models/ schemas/
    static/        Vite build output (git-ignored)
  alembic/         migrations
  scripts/         seed and OpenAPI export
  tests/
frontend/
  src/
    routes/             file-based routes (TanStack Router)
    components/ui/      shadcn components
    components/blocks/  one renderer per render-block type
    features/           auth, chat, circuit, workspace, mentoring, admin, landing
    lib/api/            typed API client generated from the OpenAPI schema
    index.css           design tokens (light and dark)
  e2e/                  Playwright tests
```
