# AI Ticketing

Internal support tickets, triaged by an LLM in seconds and routed to the right agent, with deterministic guardrails deciding what the model may auto-resolve.

> **Status: rebuild in progress (v2).** M0 (foundations), M1 (backend core) and M2 (AI triage) are built; the frontend (M3) is next. See [the PRD](docs/PRD.pdf) for the full specification and the [milestone notes](docs/milestones/).

## Stack

| Layer    | Choice                                                        |
| -------- | ------------------------------------------------------------- |
| Web      | React 19, TypeScript 5 (strict), Vite 7, Tailwind CSS v4      |
| API      | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.0 async       |
| Data     | PostgreSQL 16 (Alembic migrations), Redis 7 + ARQ job queue   |
| AI       | Groq `openai/gpt-oss-120b` behind an `LLMProvider` interface    |
| Tooling  | uv, ruff, mypy, pytest; pnpm, ESLint, Prettier, Vitest; gitleaks |

## Quick start

You need Docker, or Python 3.12 with [uv](https://docs.astral.sh/uv/) and Node 22+ with pnpm.

```bash
cp .env.example .env   # then set JWT_SECRET (32+ characters) and GROQ_API_KEY
docker compose up --build
```

Migrations run automatically before the API starts. Load the demo data once:

```bash
docker compose run --rm api python -m app.seed
```

The web app is at http://localhost:8080, the API at http://localhost:8000 and its docs at http://localhost:8000/docs.

### Demo accounts

All use the password `ticketing-demo`.

| Role      | Email                     | Sees                                    |
| --------- | ------------------------- | --------------------------------------- |
| Requester | `requester@acme.example`  | Their own tickets                       |
| Agent     | `agent@acme.example`      | Engineering tickets and their own queue |
| Admin     | `admin@acme.example`      | Everything                              |

### Without Docker for the apps

Start only Postgres and Redis in Docker (or point `.env` at hosted ones), then run each app on the host:

```bash
docker compose up -d postgres redis
cd backend && uv sync && uv run alembic upgrade head && uv run python -m app.seed
uv run uvicorn app.main:create_app --factory --reload
uv run arq app.workers.main.WorkerSettings    # triage worker, in a second terminal
cd frontend && pnpm install && pnpm dev
```

The Vite dev server on http://localhost:5173 proxies `/api` to the API on port 8000.

## Checks

These are the same commands CI runs. Backend tests need the compose Postgres and Redis running
(`docker compose up -d postgres redis`); they use their own `ticketing_test` database and Redis db 15.

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

## How triage works

The API saves each ticket as `TRIAGING` and queues a job. The worker asks the model for a
category, severity, summary, confidence and, for simple how-to questions, a draft answer.
Plain code then decides what happens: the department comes from a fixed category map,
severity can only be raised (database and infrastructure tickets are at least HIGH, and
"production down" or "data loss" makes a ticket CRITICAL), and a ticket is answered
automatically only when the model is confident, the issue is low risk, and the category is
on the allow-list. Everything else goes to the best available agent. If the model fails, the
ticket goes to a person. See [ADR 1](docs/adr/0001-worker-queue-for-triage.md) and
[ADR 2](docs/adr/0002-guardrails-decide-not-the-model.md).

### Evaluation

`backend/evals/dataset.jsonl` holds 116 hand-labeled tickets, including 10 prompt-injection
attempts and 10 vague tickets. To run them against the real model:

```bash
cd backend && uv run python -m app.evals.run --write
```

Targets: at least 90% category and department accuracy, and zero unsafe auto-resolutions.
Results go to `docs/eval-results.md`. The first real run is still pending.

## Deploy (free tiers)

| Piece | Host | Notes |
| --- | --- | --- |
| Web app | Vercel | Static Vite build; `frontend/vercel.json` proxies `/api` to Render, so cookies stay same-origin |
| API + triage worker | Render (free web service, Docker) | `backend/start-render.sh` runs migrations, the demo seed (no-op once seeded), the worker, and the API in one container |
| Redis | Render Key Value (free) | Private network, no command quota (ARQ polls Redis constantly, which would exhaust Upstash's free quota) |
| Postgres | Neon (free) | Persistent; Render's free Postgres expires after 30 days |

1. **Neon:** create a project in AWS US West (Oregon), then copy the connection string (the direct one, not "pooled").
2. **Render:** sign in with GitHub, then New > **Blueprint** > this repo. Paste the Neon string as `DATABASE_URL` and your Groq key as `GROQ_API_KEY`. `render.yaml` creates the rest.
3. **Vercel:** sign in with GitHub, then **Add New Project** > this repo, with **Root Directory** `frontend`. If Render named the API anything other than `ai-ticketing-api`, update the URL in `frontend/vercel.json` first.

Free Render services sleep after 15 minutes idle; the first request after that takes about a minute.
Registration is off on the live demo (`ALLOW_REGISTRATION=false`); use the demo accounts.

## Repository layout

```
backend/    FastAPI service: app/{api,core,db,schemas,services,llm,workers,evals}, tests/
frontend/   React + Vite single-page app
docs/       PRD, milestone notes, ADRs
.github/    CI workflows
```

## License

[MIT](LICENSE)
