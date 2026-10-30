# M1 Backend core

## Done

- **Data model:** the nine tables from the PRD in one Alembic migration, with Postgres enum types mirrored as Python `StrEnum`s, UUIDv7 ids, `timestamptz` everywhere, and the `TKT-1001…` number sequence. A test upgrades, downgrades and re-upgrades an empty database and checks the models match the migration.
- **Auth (FR-1):** register (Requester by default), login, refresh, logout, `/auth/me`. Argon2 passwords; 15-minute JWT access tokens; 7-day refresh tokens in an `HttpOnly`, `SameSite=Lax` cookie scoped to `/api/v1/auth`, stored only as SHA-256 hashes and rotated on every use. Replaying a rotated refresh token revokes every session for that user. Five failed logins lock the email for 15 minutes.
- **RBAC:** every route declares its role; ticket reads and writes are filtered by the caller's scope in the service layer. Tickets a caller cannot see return 404, not 403.
- **Tickets (FR-2, FR-3, FR-5, FR-7, FR-9):** create (saved as `TRIAGING`, then queued for triage; if the queue is down the ticket falls back to `NEW` and Unassigned), list with filters, title search, four sorts, overdue-first ordering and cursor pagination, detail, status changes through the state machine (409 `INVALID_TRANSITION` otherwise), reassign with a logged reason, reopen with re-routing, feedback on auto-resolutions, public replies and internal notes, timeline, and admin re-triage. Ticket creation is limited to 10 an hour per user.
- **Routing (FR-4):** `3 x matched skills - open tickets - 2 if BUSY`, on normalized skill tags. Agents on leave or deactivated are never candidates; open load is always a query. Ties go to the lighter load, then by name.
- **Employees (FR-6):** directory with live open load, admin create/update, agents set their own availability, deactivation returns open tickets to Unassigned and ends the agent's sessions.
- **Seed:** `python -m app.seed [--reset]` builds 6 departments, 12 agents, 3 demo logins and 40 tickets with pre-computed triage. It is idempotent and produces the same assignments every run.
- **Tests:** 130 tests, 97% line coverage, against real Postgres and Redis. CI runs them with service containers.

## Decisions worth knowing

- **Status transitions.** Agents can move `NEW → IN_PROGRESS / WAITING_ON_REQUESTER / RESOLVED / CLOSED`, `IN_PROGRESS ↔ WAITING_ON_REQUESTER`, either to `RESOLVED`, and `RESOLVED / AUTO_RESOLVED → CLOSED`. Only the system can move `TRIAGING → NEW / AUTO_RESOLVED`, reopen to `NEW`, or put a ticket back into `TRIAGING` for re-triage. The table lives in `app/services/workflow.py`.
- **Rate limiting** uses a small Redis fixed-window counter (`app/core/rate_limit.py`) instead of slowapi: the login limit is keyed by the email in the request body and counts only failures, which slowapi's decorator model doesn't fit well.
- **Requesters do not see the AI confidence score**; it is shown to agents and admins.

## Not yet

- The triage worker. New tickets wait in `TRIAGING` until M2 adds it.
- The 7-day auto-close of resolved tickets (an ARQ cron job in M2).
- Analytics endpoints (FR-8), which the M3 dashboard needs.
