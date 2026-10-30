from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import (
    AdminUser,
    CurrentUser,
    LimiterDep,
    QueueDep,
    SessionDep,
    SettingsDep,
    StaffUser,
)
from app.core.clock import utcnow
from app.core.rate_limit import Limit
from app.db.enums import Category, Role, Severity, TicketStatus
from app.db.models import Ticket, User
from app.schemas.common import Page
from app.schemas.tickets import (
    AssigneeIn,
    CommentIn,
    EventOut,
    FeedbackIn,
    StatusIn,
    TicketCreatedOut,
    TicketCreateIn,
    TicketOut,
    TicketSort,
    TicketSummaryOut,
)
from app.services import ticket_service
from app.services.ticket_service import TicketFilters

router = APIRouter(prefix="/tickets", tags=["tickets"])


def ticket_filters(
    status: Annotated[list[TicketStatus], Query()] = [],  # noqa: B006
    severity: Annotated[list[Severity], Query()] = [],  # noqa: B006
    category: Annotated[list[Category], Query()] = [],  # noqa: B006
    department_id: UUID | None = None,
    assignee_id: UUID | None = None,
    unassigned: bool | None = None,
    requester_id: UUID | None = None,
    q: Annotated[str | None, Query(max_length=150)] = None,
    overdue: bool | None = None,
    sort: TicketSort = "-created_at",
) -> TicketFilters:
    return TicketFilters(
        status=status,
        severity=severity,
        category=category,
        department_id=department_id,
        assignee_id=assignee_id,
        unassigned=unassigned,
        requester_id=requester_id,
        q=q.strip() if q and q.strip() else None,
        overdue=overdue,
        sort=sort,
    )


def summary_out(ticket: Ticket, now: datetime) -> TicketSummaryOut:
    out = TicketSummaryOut.model_validate(ticket)
    out.is_overdue = ticket_service.is_overdue(ticket, now)
    return out


async def detail_out(session: SessionDep, ticket: Ticket, viewer: User) -> TicketOut:
    out = TicketOut.model_validate(ticket)
    out.is_overdue = ticket_service.is_overdue(ticket, utcnow())
    out.feedback_given = await ticket_service.has_feedback(session, ticket.id)
    if viewer.role is Role.REQUESTER:
        # Model confidence is an agent tool; requesters see the answer, not the score.
        out.ai_confidence = None
    return out


@router.post("", response_model=TicketCreatedOut, status_code=status.HTTP_201_CREATED)
async def create_ticket(
    body: TicketCreateIn,
    user: CurrentUser,
    session: SessionDep,
    queue: QueueDep,
    limiter: LimiterDep,
    settings: SettingsDep,
) -> TicketCreatedOut:
    await limiter.consume(
        Limit("ticket-create", settings.ticket_create_limit_per_hour, 3600),
        str(user.id),
        f"You can submit up to {settings.ticket_create_limit_per_hour} tickets an hour. "
        "Try again later.",
    )
    ticket = await ticket_service.create_ticket(session, queue, user, body.title, body.description)
    return TicketCreatedOut.model_validate(ticket)


@router.get("", response_model=Page[TicketSummaryOut])
async def list_tickets(
    user: CurrentUser,
    session: SessionDep,
    filters: Annotated[TicketFilters, Depends(ticket_filters)],
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    cursor: Annotated[str | None, Query(max_length=500)] = None,
) -> Page[TicketSummaryOut]:
    tickets, next_cursor, now = await ticket_service.list_tickets(
        session, user, filters, limit, cursor
    )
    return Page(items=[summary_out(t, now) for t in tickets], next_cursor=next_cursor)


@router.get("/{ticket_id}", response_model=TicketOut)
async def get_ticket(ticket_id: UUID, user: CurrentUser, session: SessionDep) -> TicketOut:
    ticket = await ticket_service.get_visible(session, user, ticket_id)
    return await detail_out(session, ticket, user)


@router.patch("/{ticket_id}/status", response_model=TicketOut)
async def change_status(
    ticket_id: UUID, body: StatusIn, user: StaffUser, session: SessionDep
) -> TicketOut:
    ticket = await ticket_service.change_status(session, user, ticket_id, body.status)
    return await detail_out(session, ticket, user)


@router.patch("/{ticket_id}/assignee", response_model=TicketOut)
async def reassign(
    ticket_id: UUID, body: AssigneeIn, user: StaffUser, session: SessionDep
) -> TicketOut:
    ticket = await ticket_service.reassign(session, user, ticket_id, body.assignee_id, body.reason)
    return await detail_out(session, ticket, user)


@router.post("/{ticket_id}/reopen", response_model=TicketOut)
async def reopen(ticket_id: UUID, user: CurrentUser, session: SessionDep) -> TicketOut:
    ticket = await ticket_service.reopen(session, user, ticket_id)
    return await detail_out(session, ticket, user)


@router.post("/{ticket_id}/feedback", response_model=TicketOut)
async def feedback(
    ticket_id: UUID, body: FeedbackIn, user: CurrentUser, session: SessionDep
) -> TicketOut:
    ticket = await ticket_service.give_feedback(session, user, ticket_id, body.helpful)
    return await detail_out(session, ticket, user)


@router.get("/{ticket_id}/events", response_model=list[EventOut])
async def list_events(ticket_id: UUID, user: CurrentUser, session: SessionDep) -> list[EventOut]:
    events = await ticket_service.list_events(session, user, ticket_id)
    return [EventOut.model_validate(e) for e in events]


@router.post("/{ticket_id}/comments", response_model=EventOut, status_code=status.HTTP_201_CREATED)
async def add_comment(
    ticket_id: UUID, body: CommentIn, user: CurrentUser, session: SessionDep
) -> EventOut:
    event = await ticket_service.add_comment(session, user, ticket_id, body.body, body.is_internal)
    return EventOut.model_validate(event)


@router.post("/{ticket_id}/retriage", response_model=TicketOut)
async def retriage(
    ticket_id: UUID, user: AdminUser, session: SessionDep, queue: QueueDep
) -> TicketOut:
    ticket = await ticket_service.retriage(session, queue, user, ticket_id)
    return await detail_out(session, ticket, user)
