# M0 Foundations

## Done

- Monorepo: `backend/` (uv, Python 3.12) and `frontend/` (pnpm, Vite 7, React 19, TypeScript 5 strict).
- API skeleton: settings that refuse to start without `DATABASE_URL`, `REDIS_URL` and a 32+ character `JWT_SECRET`; one JSON error shape with `request_id`; `X-Request-ID` echoed and bound to structured logs; `/api/v1/health` (liveness) and `/api/v1/ready` (checks Postgres and Redis, 503 when either is down).
- Web skeleton: Tailwind v4 with light/dark theme tokens defaulting to the OS setting, and a placeholder page that shows whether the API answers.
- `docker-compose.yml` with Postgres 16, Redis 7, the API and the web app (nginx serving the build and proxying `/api`).
- CI: backend lint, format, mypy and pytest; frontend lint, format, typecheck, tests and build; gitleaks secret scan. pre-commit runs the same linters and gitleaks locally.
- Git author set to the real GitHub identity.

## Still to do by hand

- **Revoke the Groq key in v1's git history** at https://console.groq.com/keys. It is public on GitHub, so removing it from the code does not help. Put the new key only in `.env`.
- Turn on branch protection for `main` once the repo is on GitHub: require the CI checks to pass and use squash merges.

## Next: M1 backend core

SQLAlchemy models and the first Alembic migration, deterministic seed CLI, auth with rotating refresh tokens and RBAC, ticket create/list/detail with the status state machine, and the routing scorer, with tests to 80% coverage.
