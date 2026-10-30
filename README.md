# AI Ticketing

Internal support tickets, triaged by an LLM in seconds and routed to the right agent, with deterministic guardrails deciding what the model may auto-resolve.

> **Status: rebuild in progress (v2).** Milestone M0 (foundations) is done. See [the PRD](docs/PRD.pdf) for the full specification and the [milestone notes](docs/milestones/).

## Stack

| Layer    | Choice                                                        |
| -------- | ------------------------------------------------------------- |
| Web      | React 19, TypeScript 5 (strict), Vite 7, Tailwind CSS v4      |
| API      | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.0 async       |
| Data     | PostgreSQL 16 (Alembic migrations), Redis 7 + ARQ job queue   |
| AI       | Groq `llama-3.3-70b-versatile` behind an `LLMProvider` interface |
| Tooling  | uv, ruff, mypy, pytest; pnpm, ESLint, Prettier, Vitest; gitleaks |

## Quick start

You need Docker, or Python 3.12 with [uv](https://docs.astral.sh/uv/) and Node 22+ with pnpm.

```bash
cp .env.example .env   # then set JWT_SECRET (32+ characters)
docker compose up --build
```

The web app is at http://localhost:8080, the API at http://localhost:8000 and its docs at http://localhost:8000/docs.

### Without Docker for the apps

Start only Postgres and Redis in Docker (or point `.env` at hosted ones), then run each app on the host:

```bash
docker compose up -d postgres redis
cd backend && uv sync && uv run uvicorn app.main:create_app --factory --reload
cd frontend && pnpm install && pnpm dev
```

The Vite dev server on http://localhost:5173 proxies `/api` to the API on port 8000.

## Checks

These are the same commands CI runs.

```bash
cd backend
uv run ruff check . && uv run ruff format --check .
uv run mypy app tests
uv run pytest --cov
```

```bash
cd frontend
pnpm lint && pnpm format:check && pnpm typecheck
pnpm test
pnpm build
```

## Repository layout

```
backend/    FastAPI service: app/{api,core,db,schemas,services,llm,workers,evals}, tests/
frontend/   React + Vite single-page app
docs/       PRD, milestone notes, ADRs
.github/    CI workflows
```

## License

[MIT](LICENSE)
