"""Ticket use cases. Every read and write is scoped to what the caller may see (section 10)."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

import structlog
from sqlalchemy import ColumnElement, and_, case, exists, func, or_, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utcnow
from app.core.errors import AppError
from app.db.enums import (
    DONE_STATUSES,
    SEVERITY_RANK,
    Availability,
    Category,
    EventType,
    Role,
    Severity,
    TicketStatus,
    TriageStatus,
)
from app.db.models import CategoryRoute, Ticket, TicketEvent, User
from app.schemas.tickets import TicketSort
from app.services import routing, workflow
from app.services.pagination import (
    SortKey,
    after_cursor,
    decode_cursor,
    next_cursor,
)
from app.workers.queue import TriageQueue

log = structlog.get_logger()

FAR_FUTURE = datetime(9999, 1, 1, tzinfo=UTC)
NO_SEVERITY_RANK = len(SEVERITY_RANK)


# ---------------------------------------------------------------- scope and permissions


def visible_to(user: User) -> ColumnElement[bool]:
    if user.role is Role.ADMIN:
        return true()
    if user.role is Role.AGENT:
        clauses = [Ticket.assignee_id == user.id, Ticket.requester_id == user.id]
        if user.department_id is not None:
            clauses.append(Ticket.department_id == user.department_id)
        return or_(*clauses)
    return Ticket.requester_id == user.id


def can_manage(user: User, ticket: Ticket) -> bool:
    if user.role is Role.ADMIN:
        return True
    if user.role is not Role.AGENT:
        return False
    return ticket.assignee_id == user.id or (
        ticket.department_id is not None and ticket.department_id == user.department_id
    )


def ensure_can_manage(user: User, ticket: Ticket) -> None:
    if not can_manage(user, ticket):
        raise AppError(403, "FORBIDDEN", "You can only work tickets in your department")


def is_overdue(ticket: Ticket, now: datetime) -> bool:
    return (
        ticket.resolve_due_at is not None
        and ticket.resolve_due_at < now
        and ticket.status not in DONE_STATUSES
    )


async def get_visible(session: AsyncSession, user: User, ticket_id: UUID) -> Ticket:
    ticket = await session.scalar(select(Ticket).where(Ticket.id == ticket_id, visible_to(user)))
    if ticket is None:
        # 404 rather than 403, so ticket ids reveal nothing to people who cannot see them.
        raise AppError(404, "NOT_FOUND", "Ticket not found")
    return ticket


# ---------------------------------------------------------------- events


def add_event(
    session: AsyncSession,
    ticket: Ticket,
    event_type: EventType,
    actor: User | None,
    *,
    from_value: str | None = None,
    to_value: str | None = None,
    body: str | None = None,
    is_internal: bool = False,
) -> TicketEvent:
    event = TicketEvent(
        ticket_id=ticket.id,
        actor_id=actor.id if actor else None,
        type=event_type,
        from_value=from_value,
        to_value=to_value,
        body=body,
        is_internal=is_internal,
    )
    session.add(event)
    return event


def set_status(
    session: AsyncSession,
    ticket: Ticket,
    target: TicketStatus,
    actor: User | None,
    *,
    system: bool = False,
) -> None:
    workflow.ensure_transition(ticket.status, target, system=system)
    previous = ticket.status
    ticket.status = target
    now = utcnow()
    if target in (TicketStatus.RESOLVED, TicketStatus.AUTO_RESOLVED):
        ticket.resolved_at = now
    elif target is TicketStatus.CLOSED:
        ticket.closed_at = now
    elif target is TicketStatus.NEW and previous in workflow.REOPENABLE:
        ticket.resolved_at = None
    add_event(
        session,
        ticket,
        EventType.STATUS_CHANGED,
        actor,
        from_value=previous.value,
        to_value=target.value,
    )


# ---------------------------------------------------------------- create


async def create_ticket(
    session: AsyncSession, queue: TriageQueue, requester: User, title: str, description: str
) -> Ticket:
    """Persist first, then hand off to triage. A ticket is never lost to a queue failure."""
    ticket = Ticket(
        title=title,
        description=description,
        requester_id=requester.id,
        status=TicketStatus.TRIAGING,
        triage_status=TriageStatus.PENDING,
    )
    session.add(ticket)
    await session.flush()
    add_event(session, ticket, EventType.CREATED, requester)
    await session.commit()

    try:
        await queue.enqueue_triage(ticket.id)
    except Exception:
        log.exception("triage_enqueue_failed", ticket_id=str(ticket.id))
        await mark_triage_failed(session, ticket)

    await session.refresh(ticket)
    return ticket


async def mark_triage_failed(session: AsyncSession, ticket: Ticket) -> None:
    """Fallback: the ticket goes to the Unassigned queue for a person to review."""
    ticket.triage_status = TriageStatus.FAILED
    if ticket.status is TicketStatus.TRIAGING:
        set_status(session, ticket, TicketStatus.NEW, None, system=True)
    await session.commit()


# ---------------------------------------------------------------- list


@dataclass
class TicketFilters:
    status: list[TicketStatus] = field(default_factory=list)
    severity: list[Severity] = field(default_factory=list)
    category: list[Category] = field(default_factory=list)
    department_id: UUID | None = None
    assignee_id: UUID | None = None
    unassigned: bool | None = None
    requester_id: UUID | None = None
    q: str | None = None
    overdue: bool | None = None
    sort: TicketSort = "-created_at"


def sort_keys(sort: TicketSort, now: datetime) -> list[SortKey[Ticket]]:
    overdue_expr = case(
        (
            and_(
                Ticket.resolve_due_at.is_not(None),
                Ticket.resolve_due_at < now,
                Ticket.status.not_in(DONE_STATUSES),
            ),
            1,
        ),
        else_=0,
    )
    keys: list[SortKey[Ticket]] = [
        # Overdue tickets always sort first (FR-7).
        SortKey(overdue_expr, True, lambda t: int(is_overdue(t, now)))
    ]
    if sort == "created_at":
        keys.append(SortKey(Ticket.created_at, False, lambda t: t.created_at))
    elif sort == "due":
        keys.append(
            SortKey(
                func.coalesce(Ticket.resolve_due_at, FAR_FUTURE),
                False,
                lambda t: t.resolve_due_at or FAR_FUTURE,
            )
        )
    elif sort == "severity":
        rank = case(
            *[(Ticket.severity == sev, r) for sev, r in SEVERITY_RANK.items()],
            else_=NO_SEVERITY_RANK,
        )
        keys.append(
            SortKey(
                rank,
                False,
                lambda t: SEVERITY_RANK[t.severity] if t.severity else NO_SEVERITY_RANK,
            )
        )
    else:
        keys.append(SortKey(Ticket.created_at, True, lambda t: t.created_at))
    keys.append(SortKey(Ticket.id, True, lambda t: t.id))
    return keys


def _filter_clauses(filters: TicketFilters, now: datetime) -> list[ColumnElement[bool]]:
    clauses: list[ColumnElement[bool]] = []
    if filters.status:
        clauses.append(Ticket.status.in_(filters.status))
    if filters.severity:
        clauses.append(Ticket.severity.in_(filters.severity))
    if filters.category:
        clauses.append(Ticket.category.in_(filters.category))
    if filters.department_id:
        clauses.append(Ticket.department_id == filters.department_id)
    if filters.assignee_id:
        clauses.append(Ticket.assignee_id == filters.assignee_id)
    if filters.unassigned is not None:
        clauses.append(
            Ticket.assignee_id.is_(None) if filters.unassigned else Ticket.assignee_id.is_not(None)
        )
    if filters.requester_id:
        clauses.append(Ticket.requester_id == filters.requester_id)
    if filters.q:
        escaped = filters.q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        clauses.append(Ticket.title.ilike(f"%{escaped}%", escape="\\"))
    if filters.overdue is not None:
        overdue = and_(
            Ticket.resolve_due_at.is_not(None),
            Ticket.resolve_due_at < now,
            Ticket.status.not_in(DONE_STATUSES),
        )
        clauses.append(overdue if filters.overdue else ~overdue)
    return clauses


async def list_tickets(
    session: AsyncSession,
    user: User,
    filters: TicketFilters,
    limit: int,
    cursor: str | None,
) -> tuple[list[Ticket], str | None, datetime]:
    now = utcnow()
    keys = sort_keys(filters.sort, now)
    query = select(Ticket).where(visible_to(user), *_filter_clauses(filters, now))
    if cursor:
        query = query.where(after_cursor(keys, decode_cursor(cursor, len(keys))))
    query = query.order_by(*(k.order_by() for k in keys)).limit(limit + 1)
    rows = list((await session.scalars(query)).unique())
    return rows[:limit], next_cursor(keys, rows, limit), now


# ---------------------------------------------------------------- workflow actions


async def change_status(
    session: AsyncSession, actor: User, ticket_id: UUID, target: TicketStatus
) -> Ticket:
    ticket = await get_visible(session, actor, ticket_id)
    ensure_can_manage(actor, ticket)
    set_status(session, ticket, target, actor)
    await session.commit()
    await session.refresh(ticket)
    return ticket


async def reassign(
    session: AsyncSession, actor: User, ticket_id: UUID, assignee_id: UUID | None, reason: str
) -> Ticket:
    ticket = await get_visible(session, actor, ticket_id)
    ensure_can_manage(actor, ticket)
    if ticket.status in DONE_STATUSES or ticket.status is TicketStatus.TRIAGING:
        raise AppError(409, "NOT_ASSIGNABLE", "Only open tickets can be reassigned")

    assignee: User | None = None
    if assignee_id is not None:
        assignee = await session.get(User, assignee_id)
        if (
            assignee is None
            or not assignee.is_active
            or assignee.role is not Role.AGENT
            or assignee.department_id is None
        ):
            raise AppError(422, "INVALID_ASSIGNEE", "Tickets can only go to active agents")
        if assignee.availability is Availability.ON_LEAVE:
            raise AppError(422, "INVALID_ASSIGNEE", f"{assignee.full_name} is on leave")
        if actor.role is Role.AGENT and assignee.department_id != actor.department_id:
            raise AppError(403, "FORBIDDEN", "Agents can only reassign within their department")

    previous = ticket.assignee
    ticket.assignee_id = assignee.id if assignee else None
    if assignee is not None:
        ticket.department_id = assignee.department_id
    add_event(
        session,
        ticket,
        EventType.ASSIGNED,
        actor,
        from_value=previous.full_name if previous else None,
        to_value=assignee.full_name if assignee else None,
        body=reason,
    )
    await session.commit()
    await session.refresh(ticket)
    return ticket


async def route_ticket(session: AsyncSession, ticket: Ticket) -> None:
    """Assign to the best available agent in the ticket's department, if there is one."""
    ticket.assignee_id = None
    if ticket.department_id is None:
        return
    wanted: set[str] = set()
    if ticket.category is not None:
        route = await session.scalar(
            select(CategoryRoute).where(CategoryRoute.category == ticket.category)
        )
        wanted = set(route.default_skills) if route else set()
    assignee_id = await routing.choose_assignee(session, ticket.department_id, wanted)
    if assignee_id is not None:
        ticket.assignee_id = assignee_id
        assignee = await session.get(User, assignee_id)
        add_event(
            session,
            ticket,
            EventType.ASSIGNED,
            None,
            to_value=assignee.full_name if assignee else None,
            body="Routed automatically",
        )


async def reopen(session: AsyncSession, actor: User, ticket_id: UUID) -> Ticket:
    ticket = await get_visible(session, actor, ticket_id)
    if actor.role is not Role.ADMIN and ticket.requester_id != actor.id:
        raise AppError(403, "FORBIDDEN", "Only the requester can reopen this ticket")
    await _reopen(session, ticket, actor)
    await session.commit()
    await session.refresh(ticket)
    return ticket


async def _reopen(session: AsyncSession, ticket: Ticket, actor: User) -> None:
    if ticket.status not in workflow.REOPENABLE:
        raise AppError(
            409,
            "INVALID_TRANSITION",
            f"Cannot reopen a ticket that is {ticket.status.value}",
            {"from": ticket.status.value, "to": TicketStatus.NEW.value},
        )
    previous = ticket.status
    set_status(session, ticket, TicketStatus.NEW, actor, system=True)
    add_event(session, ticket, EventType.REOPENED, actor, from_value=previous.value)
    await route_ticket(session, ticket)


async def has_feedback(session: AsyncSession, ticket_id: UUID) -> bool:
    result = await session.scalar(
        select(
            exists().where(
                TicketEvent.ticket_id == ticket_id, TicketEvent.type == EventType.FEEDBACK
            )
        )
    )
    return bool(result)


async def give_feedback(
    session: AsyncSession, actor: User, ticket_id: UUID, helpful: bool
) -> Ticket:
    ticket = await get_visible(session, actor, ticket_id)
    if ticket.requester_id != actor.id:
        raise AppError(403, "FORBIDDEN", "Only the requester can rate this answer")
    if ticket.status is not TicketStatus.AUTO_RESOLVED:
        raise AppError(409, "NOT_AUTO_RESOLVED", "Only automatic answers can be rated")
    if await has_feedback(session, ticket.id):
        raise AppError(409, "FEEDBACK_EXISTS", "You already rated this answer")

    add_event(
        session,
        ticket,
        EventType.FEEDBACK,
        actor,
        to_value="helpful" if helpful else "not_helpful",
    )
    if not helpful:
        await _reopen(session, ticket, actor)
    await session.commit()
    await session.refresh(ticket)
    return ticket


async def add_comment(
    session: AsyncSession, actor: User, ticket_id: UUID, body: str, is_internal: bool
) -> TicketEvent:
    ticket = await get_visible(session, actor, ticket_id)
    staff = actor.role in (Role.AGENT, Role.ADMIN)
    if is_internal and not staff:
        raise AppError(403, "FORBIDDEN", "Only agents can add internal notes")
    if staff and ticket.requester_id != actor.id:
        ensure_can_manage(actor, ticket)
    if ticket.status is TicketStatus.CLOSED:
        raise AppError(409, "TICKET_CLOSED", "This ticket is closed")

    event = add_event(
        session,
        ticket,
        EventType.NOTE if is_internal else EventType.REPLY,
        actor,
        body=body,
        is_internal=is_internal,
    )
    if staff and not is_internal and ticket.first_responded_at is None:
        ticket.first_responded_at = utcnow()
    await session.commit()
    await session.refresh(event)
    return event


async def list_events(session: AsyncSession, actor: User, ticket_id: UUID) -> list[TicketEvent]:
    await get_visible(session, actor, ticket_id)
    query = select(TicketEvent).where(TicketEvent.ticket_id == ticket_id)
    if actor.role is Role.REQUESTER:
        # Internal notes never reach a requester, whatever the client asks for.
        query = query.where(TicketEvent.is_internal.is_(False))
    query = query.order_by(TicketEvent.created_at, TicketEvent.id)
    return list((await session.scalars(query)).unique())


async def retriage(
    session: AsyncSession, queue: TriageQueue, actor: User, ticket_id: UUID
) -> Ticket:
    ticket = await get_visible(session, actor, ticket_id)
    if ticket.status not in (TicketStatus.NEW, TicketStatus.TRIAGING):
        raise AppError(409, "NOT_RETRIAGEABLE", "Only new tickets can be triaged again")
    ticket.triage_status = TriageStatus.PENDING
    if ticket.status is TicketStatus.NEW:
        set_status(session, ticket, TicketStatus.TRIAGING, actor, system=True)
    await session.commit()
    try:
        await queue.enqueue_triage(ticket.id)
    except Exception:
        log.exception("triage_enqueue_failed", ticket_id=str(ticket.id))
        await mark_triage_failed(session, ticket)
    await session.refresh(ticket)
    return ticket


async def unassign_open_tickets(session: AsyncSession, actor: User, agent: User) -> int:
    """Return a deactivated agent's open tickets to the Unassigned queue."""
    tickets = (
        await session.scalars(
            select(Ticket).where(
                Ticket.assignee_id == agent.id,
                Ticket.status.not_in(DONE_STATUSES),
            )
        )
    ).unique()
    count = 0
    for ticket in tickets:
        ticket.assignee_id = None
        add_event(
            session,
            ticket,
            EventType.ASSIGNED,
            actor,
            from_value=agent.full_name,
            body=f"{agent.full_name} was deactivated",
        )
        count += 1
    return count
