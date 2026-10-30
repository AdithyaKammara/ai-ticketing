"""ARQ worker: `arq app.workers.main.WorkerSettings`.

Runs AI triage off the request path, plus hourly housekeeping: auto-closing resolved
tickets after 7 days and dropping triage logs past their 90-day retention.
"""

from typing import Any, ClassVar
from uuid import UUID

import structlog
from arq import cron
from arq.connections import RedisSettings

from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.db.session import create_engine, create_sessionmaker
from app.llm.factory import build_provider
from app.llm.groq_provider import GroqProvider
from app.services import triage
from app.services.triage import TriageDeps
from app.workers.queue import TRIAGE_JOB

log = structlog.get_logger()


async def startup(ctx: dict[str, Any]) -> None:
    settings = get_settings()
    configure_logging(settings.log_level, json=settings.environment == "production")
    ctx["settings"] = settings
    ctx["engine"] = create_engine(str(settings.database_url))
    ctx["sessionmaker"] = create_sessionmaker(ctx["engine"])
    ctx["provider"] = build_provider(settings)
    log.info("worker_started", provider=ctx["provider"].name, model=ctx["provider"].model)


async def shutdown(ctx: dict[str, Any]) -> None:
    provider = ctx.get("provider")
    if isinstance(provider, GroqProvider):
        await provider.aclose()
    if "engine" in ctx:
        await ctx["engine"].dispose()


async def triage_ticket(ctx: dict[str, Any], ticket_id: str) -> str:
    structlog.contextvars.bind_contextvars(job="triage", ticket_id=ticket_id)
    deps = TriageDeps(provider=ctx["provider"], redis=ctx["redis"], settings=ctx["settings"])
    async with ctx["sessionmaker"]() as session:
        run = await triage.triage_ticket(session, UUID(ticket_id), deps)
    return run.value


async def housekeeping(ctx: dict[str, Any]) -> dict[str, int]:
    settings: Settings = ctx["settings"]
    async with ctx["sessionmaker"]() as session:
        closed = await triage.auto_close_resolved(session, settings.auto_close_after_days)
        purged = await triage.purge_old_triage_logs(session, settings.triage_log_retention_days)
    log.info("housekeeping_done", closed=closed, purged_logs=purged)
    return {"closed": closed, "purged_logs": purged}


assert triage_ticket.__name__ == TRIAGE_JOB  # the name the API enqueues


class WorkerSettings:
    functions: ClassVar = [triage_ticket]
    cron_jobs: ClassVar = [cron(housekeeping, minute=7, run_at_startup=True)]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(str(get_settings().redis_url))
    # Triage retries internally; a crashed run is retried by ARQ and is idempotent.
    max_tries = 3
    job_timeout = 120
    keep_result = 3600
