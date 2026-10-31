"""Analytics aggregations (FR-8). Every number is computed in SQL, never in a Python loop.

Scope: admins see all tickets; agents see only their own department. A date range [frm, to)
bounds each query on the relevant timestamp.
"""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from sqlalchemy import ColumnElement, and_, case, func, or_, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utcnow
from app.core.errors import AppError
from app.db.enums import DONE_STATUSES, EventType, Role, TicketStatus
from app.db.models import Department, Ticket, TicketEvent, User
from app.schemas.analytics import (
    AiQualityOut,
    BreakdownBucket,
    BreakdownBy,
    ConfidenceBucket,
    SummaryOut,
    VolumePoint,
)

AUTO = TicketStatus.AUTO_RESOLVED
OPEN_TICKET_STATUSES = tuple(s for s in TicketStatus if s not in DONE_STATUSES)


@dataclass(frozen=True)
class DateRange:
    frm: datetime
    to: datetime

    @classmethod
    def of(cls, frm: date | None, to: date | None) -> "DateRange":
        end = datetime.combine(to or utcnow().date(), time.max) if to else utcnow()
        start = datetime.combine(frm, time.min) if frm else end - timedelta(days=30)
        if start > end:
            raise AppError(400, "INVALID_RANGE", "The 'from' date is after the 'to' date")
        return cls(start.replace(tzinfo=utcnow().tzinfo), end.replace(tzinfo=utcnow().tzinfo))


def scope(user: User) -> ColumnElement[bool]:
    if user.role is Role.ADMIN:
        return true()
    if user.department_id is None:
        return Ticket.department_id.is_(None)
    return Ticket.department_id == user.department_id


def _created_in(rng: DateRange) -> ColumnElement[bool]:
    return and_(Ticket.created_at >= rng.frm, Ticket.created_at <= rng.to)


async def summary(session: AsyncSession, user: User, rng: DateRange) -> SummaryOut:
    s = scope(user)
    first_response_minutes = (
        func.extract("epoch", Ticket.first_responded_at - Ticket.created_at) / 60.0
    )
    breached = and_(
        Ticket.resolve_due_at.is_not(None),
        or_(
            and_(Ticket.resolved_at.is_not(None), Ticket.resolved_at > Ticket.resolve_due_at),
            and_(Ticket.resolved_at.is_(None), Ticket.resolve_due_at < utcnow()),
        ),
    )
    resolved_in_range = and_(Ticket.resolved_at >= rng.frm, Ticket.resolved_at <= rng.to)

    row = (
        await session.execute(
            select(
                func.count().filter(Ticket.status.in_(OPEN_TICKET_STATUSES)).label("open"),
                func.count().filter(resolved_in_range).label("resolved"),
                func.count()
                .filter(resolved_in_range, Ticket.status == AUTO)
                .label("auto_resolved"),
                func.percentile_cont(0.5)
                .within_group(first_response_minutes)
                .filter(Ticket.first_responded_at.is_not(None), _created_in(rng))
                .label("median_frt"),
                func.count().filter(breached, _created_in(rng)).label("breaches"),
            ).where(s)
        )
    ).one()

    resolved = row.resolved or 0
    return SummaryOut(
        open_tickets=row.open or 0,
        resolved_this_period=resolved,
        auto_resolved=row.auto_resolved or 0,
        auto_resolution_rate=round((row.auto_resolved or 0) / resolved, 4) if resolved else 0.0,
        reopen_rate=await _reopen_rate(session, user, rng),
        median_first_response_minutes=(
            round(row.median_frt, 1) if row.median_frt is not None else None
        ),
        sla_breaches=row.breaches or 0,
    )


async def _reopen_rate(session: AsyncSession, user: User, rng: DateRange) -> float:
    """Reopened auto-resolutions / auto-resolutions, by event time in range."""
    reopened = (
        select(func.count())
        .select_from(TicketEvent)
        .join(Ticket, Ticket.id == TicketEvent.ticket_id)
        .where(
            scope(user),
            TicketEvent.type == EventType.REOPENED,
            TicketEvent.from_value == AUTO.value,
            TicketEvent.created_at >= rng.frm,
            TicketEvent.created_at <= rng.to,
        )
    )
    auto = (
        select(func.count())
        .select_from(TicketEvent)
        .join(Ticket, Ticket.id == TicketEvent.ticket_id)
        .where(
            scope(user),
            TicketEvent.type == EventType.STATUS_CHANGED,
            TicketEvent.to_value == AUTO.value,
            TicketEvent.created_at >= rng.frm,
            TicketEvent.created_at <= rng.to,
        )
    )
    reopened_n = int(await session.scalar(reopened) or 0)
    auto_n = int(await session.scalar(auto) or 0)
    return round(reopened_n / auto_n, 4) if auto_n else 0.0


async def volume(session: AsyncSession, user: User, rng: DateRange) -> list[VolumePoint]:
    created_day = func.date(Ticket.created_at)
    created: dict[date, int] = dict(
        (
            await session.execute(
                select(created_day, func.count())
                .where(scope(user), _created_in(rng))
                .group_by(created_day)
            )
        ).all()
    )
    resolved_day = func.date(Ticket.resolved_at)
    resolved: dict[date, int] = dict(
        (
            await session.execute(
                select(resolved_day, func.count())
                .where(
                    scope(user),
                    Ticket.resolved_at >= rng.frm,
                    Ticket.resolved_at <= rng.to,
                )
                .group_by(resolved_day)
            )
        ).all()
    )

    days = (rng.to.date() - rng.frm.date()).days
    return [
        VolumePoint(
            day=day,
            created=int(created.get(day, 0)),
            resolved=int(resolved.get(day, 0)),
        )
        for day in (rng.frm.date() + timedelta(days=i) for i in range(days + 1))
    ]


async def breakdown(
    session: AsyncSession, user: User, rng: DateRange, by: BreakdownBy
) -> list[BreakdownBucket]:
    if by == "department":
        rows = (
            await session.execute(
                select(
                    func.coalesce(Department.slug, "unassigned"),
                    func.coalesce(Department.name, "Unassigned"),
                    func.count(),
                )
                .select_from(Ticket)
                .outerjoin(Department, Department.id == Ticket.department_id)
                .where(scope(user), _created_in(rng))
                .group_by(Department.slug, Department.name)
                .order_by(func.count().desc())
            )
        ).all()
        return [BreakdownBucket(key=k, label=lbl, count=c) for k, lbl, c in rows]

    column = Ticket.category if by == "category" else Ticket.severity
    enum_rows = (
        await session.execute(
            select(column, func.count())
            .where(scope(user), _created_in(rng), column.is_not(None))
            .group_by(column)
            .order_by(func.count().desc())
        )
    ).all()
    return [
        BreakdownBucket(key=value.value, label=value.value.replace("_", " ").title(), count=count)
        for value, count in enum_rows
        if value is not None  # the SQL filters None; this satisfies the type checker
    ]


async def ai_quality(session: AsyncSession, rng: DateRange) -> AiQualityOut:
    """Admin only: how triage is performing. Scope is always all departments."""
    bucket = case(
        (Ticket.ai_confidence < 20, "0-19"),
        (Ticket.ai_confidence < 40, "20-39"),
        (Ticket.ai_confidence < 60, "40-59"),
        (Ticket.ai_confidence < 80, "60-79"),
        (Ticket.ai_confidence < 85, "80-84"),
        else_="85-100",
    )
    triaged = and_(Ticket.triage_status.is_not(None), _created_in(rng))
    counts = (
        await session.execute(
            select(
                func.count().filter(Ticket.triage_status == "DONE").label("done"),
                func.count().filter(Ticket.status == AUTO).label("auto"),
                func.count().filter(Ticket.triage_status == "FAILED").label("failed"),
                func.count().filter(Ticket.ai_confidence.is_not(None)).label("confident"),
            ).where(triaged)
        )
    ).one()
    hist = (
        await session.execute(
            select(bucket, func.count())
            .where(_created_in(rng), Ticket.ai_confidence.is_not(None))
            .group_by(bucket)
        )
    ).all()
    order = ["0-19", "20-39", "40-59", "60-79", "80-84", "85-100"]
    hist_map = {b: int(c) for b, c in hist}

    done = counts.done or 0
    auto = counts.auto or 0
    routed = done - auto
    rate = await _reopen_and_helpful(session, rng)
    return AiQualityOut(
        triaged=done + (counts.failed or 0),
        auto_resolved=auto,
        routed=routed,
        failed=counts.failed or 0,
        auto_resolution_rate=round(auto / done, 4) if done else 0.0,
        reopen_rate=rate[0],
        helpful_rate=rate[1],
        confidence_histogram=[ConfidenceBucket(bucket=b, count=hist_map.get(b, 0)) for b in order],
    )


async def _reopen_and_helpful(session: AsyncSession, rng: DateRange) -> tuple[float, float | None]:
    in_range = and_(TicketEvent.created_at >= rng.frm, TicketEvent.created_at <= rng.to)
    row = (
        await session.execute(
            select(
                func.count()
                .filter(
                    TicketEvent.type == EventType.STATUS_CHANGED,
                    TicketEvent.to_value == AUTO.value,
                )
                .label("auto"),
                func.count()
                .filter(
                    TicketEvent.type == EventType.REOPENED,
                    TicketEvent.from_value == AUTO.value,
                )
                .label("reopened"),
                func.count()
                .filter(
                    TicketEvent.type == EventType.FEEDBACK,
                    TicketEvent.to_value == "helpful",
                )
                .label("helpful"),
                func.count().filter(TicketEvent.type == EventType.FEEDBACK).label("votes"),
            ).where(in_range)
        )
    ).one()
    auto = row.auto or 0
    votes = row.votes or 0
    reopen_rate = round((row.reopened or 0) / auto, 4) if auto else 0.0
    helpful_rate = round((row.helpful or 0) / votes, 4) if votes else None
    return reopen_rate, helpful_rate
