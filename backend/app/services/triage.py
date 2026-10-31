"""Applying triage to a ticket (section 5, steps 1-5).

Order: lock the ticket, check the daily budget, ask the model, then let deterministic code
pick the department, severity floor, auto-resolve vs route, assignee and SLA. Every run
writes one ai_triage_logs row, whatever happened.
"""

from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum
from uuid import UUID

import structlog
from redis.asyncio import Redis
from sqlalchemy import delete, exists, select
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity.wait import WaitBaseT

from app.core.clock import utcnow
from app.core.config import Settings
from app.db.enums import (
    Category,
    EventType,
    Sentiment,
    Severity,
    TicketStatus,
    TriageStatus,
)
from app.db.models import AiTriageLog, CategoryRoute, Ticket, TicketEvent, User
from app.llm.base import LLMProvider
from app.llm.prompts.triage_v3 import RouteInfo
from app.services import guardrails, routing, sla, ticket_service
from app.services.guardrails import Decision, GuardrailInput
from app.services.skills import normalize_skills
from app.services.triage_model import DEFAULT_WAIT, PROMPT_VERSION, run_triage_model

log = structlog.get_logger()

REOPEN_LOOKBACK = timedelta(hours=24)


class TriageRun(StrEnum):
    AUTO_RESOLVED = "AUTO_RESOLVED"
    ROUTED = "ROUTED"
    FAILED = "FAILED"
    SKIPPED_BUDGET = "SKIPPED_BUDGET"
    NOT_TRIAGING = "NOT_TRIAGING"


@dataclass(frozen=True)
class TriageDeps:
    provider: LLMProvider
    redis: Redis
    settings: Settings
    wait: WaitBaseT = DEFAULT_WAIT


async def within_daily_budget(redis: Redis, budget: int) -> bool:
    """Count one model call against today's global budget (UTC)."""
    key = f"llm:calls:{utcnow():%Y-%m-%d}"
    async with redis.pipeline(transaction=True) as pipe:
        pipe.incr(key)
        pipe.expire(key, 2 * 24 * 3600, nx=True)
        count, _ = await pipe.execute()
    return int(count) <= budget


async def recently_reopened_auto_resolution(session: AsyncSession, requester_id: UUID) -> bool:
    result = await session.scalar(
        select(
            exists().where(
                TicketEvent.type == EventType.REOPENED,
                TicketEvent.actor_id == requester_id,
                TicketEvent.from_value == TicketStatus.AUTO_RESOLVED.value,
                TicketEvent.created_at >= utcnow() - REOPEN_LOOKBACK,
            )
        )
    )
    return bool(result)


async def load_routes(session: AsyncSession) -> dict[Category, CategoryRoute]:
    rows = await session.scalars(select(CategoryRoute))
    return {route.category: route for route in rows.unique()}


async def triage_ticket(session: AsyncSession, ticket_id: UUID, deps: TriageDeps) -> TriageRun:
    # The row lock makes a duplicate job for the same ticket wait, then see it is done.
    ticket = await session.scalar(
        select(Ticket).where(Ticket.id == ticket_id).with_for_update(of=Ticket)
    )
    if ticket is None or ticket.status is not TicketStatus.TRIAGING:
        await session.rollback()
        return TriageRun.NOT_TRIAGING

    if not await within_daily_budget(deps.redis, deps.settings.llm_daily_budget):
        ticket.triage_status = TriageStatus.SKIPPED
        ticket_service.set_status(session, ticket, TicketStatus.NEW, None, system=True)
        session.add(
            AiTriageLog(
                ticket_id=ticket.id,
                provider=deps.provider.name,
                model=deps.provider.model,
                prompt_version=PROMPT_VERSION,
                error="daily LLM budget reached; sent to a person",
                guardrail_decision=TriageRun.SKIPPED_BUDGET.value,
            )
        )
        await session.commit()
        log.warning("triage_skipped_budget", ticket_id=str(ticket.id))
        return TriageRun.SKIPPED_BUDGET

    routes = await load_routes(session)
    route_info = [RouteInfo(c, r.department.name) for c, r in routes.items()]
    outcome = await run_triage_model(
        deps.provider, ticket.title, ticket.description, route_info, wait=deps.wait
    )
    triage_log = AiTriageLog(
        ticket_id=ticket.id,
        provider=outcome.provider,
        model=outcome.model,
        prompt_version=PROMPT_VERSION,
        latency_ms=outcome.latency_ms,
        input_tokens=outcome.input_tokens,
        output_tokens=outcome.output_tokens,
        raw_output=outcome.raw_output,
        error=outcome.error,
    )
    session.add(triage_log)

    result = outcome.result
    category = Category(result.category) if result else None
    route = routes.get(category) if category else None
    if result is None or category is None or route is None:
        triage_log.guardrail_decision = TriageRun.FAILED.value
        if result is not None:
            triage_log.error = f"no route configured for category {result.category}"
        await ticket_service.mark_triage_failed(session, ticket)
        log.warning("triage_failed", ticket_id=str(ticket.id), error=triage_log.error)
        return TriageRun.FAILED

    severity = guardrails.apply_severity_floor(
        Severity(result.severity), route.severity_floor, ticket.title, ticket.description
    )
    verdict = guardrails.decide(
        GuardrailInput(
            category=category,
            severity=severity,
            can_self_serve=result.can_self_serve,
            draft_response=result.draft_response,
            confidence=result.confidence,
            category_allows_auto_resolve=route.auto_resolve_allowed,
            min_confidence=deps.settings.auto_resolve_min_confidence,
            recently_reopened_auto_resolution=await recently_reopened_auto_resolution(
                session, ticket.requester_id
            ),
        )
    )
    triage_log.parsed = {
        **result.model_dump(),
        "final_severity": severity.value,
        "guardrail_reasons": verdict.reasons,
    }
    triage_log.guardrail_decision = verdict.decision.value

    ticket.category = category
    ticket.severity = severity
    ticket.sentiment = Sentiment(result.sentiment)
    ticket.ai_summary = result.summary
    ticket.ai_confidence = result.confidence
    ticket.department_id = route.department_id
    ticket.triage_status = TriageStatus.DONE
    ticket.first_response_due_at, ticket.resolve_due_at = sla.due_times(severity, ticket.created_at)
    ticket_service.add_event(session, ticket, EventType.TRIAGED, None, to_value=category.value)

    if verdict.decision is Decision.AUTO_RESOLVE:
        ticket.auto_response = result.draft_response
        ticket_service.set_status(session, ticket, TicketStatus.AUTO_RESOLVED, None, system=True)
        run = TriageRun.AUTO_RESOLVED
    else:
        ticket_service.set_status(session, ticket, TicketStatus.NEW, None, system=True)
        wanted = normalize_skills(result.suggested_skills) | set(route.default_skills)
        assignee_id = await routing.choose_assignee(session, route.department_id, wanted)
        if assignee_id is not None:
            ticket.assignee_id = assignee_id
            assignee = await session.get(User, assignee_id)
            ticket_service.add_event(
                session,
                ticket,
                EventType.ASSIGNED,
                None,
                to_value=assignee.full_name if assignee else None,
                body="Routed automatically",
            )
        run = TriageRun.ROUTED

    await session.commit()
    log.info(
        "triage_done",
        ticket_id=str(ticket.id),
        decision=run.value,
        category=category.value,
        severity=severity.value,
        confidence=result.confidence,
        latency_ms=outcome.latency_ms,
    )
    return run


async def auto_close_resolved(session: AsyncSession, after_days: int) -> int:
    """Close resolved tickets nobody reopened within `after_days` (FR-3)."""
    cutoff = utcnow() - timedelta(days=after_days)
    tickets = (
        await session.scalars(
            select(Ticket)
            .where(
                Ticket.status.in_((TicketStatus.RESOLVED, TicketStatus.AUTO_RESOLVED)),
                Ticket.resolved_at < cutoff,
            )
            .limit(500)
            .with_for_update(of=Ticket, skip_locked=True)
        )
    ).unique()
    closed = 0
    for ticket in tickets:
        ticket_service.set_status(session, ticket, TicketStatus.CLOSED, None, system=True)
        closed += 1
    await session.commit()
    return closed


async def purge_old_triage_logs(session: AsyncSession, retention_days: int) -> int:
    result = await session.execute(
        delete(AiTriageLog).where(
            AiTriageLog.created_at < utcnow() - timedelta(days=retention_days)
        )
    )
    await session.commit()
    return int(result.rowcount or 0)  # type: ignore[attr-defined]
