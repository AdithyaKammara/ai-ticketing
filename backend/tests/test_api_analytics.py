"""Analytics endpoints (FR-8): scope, KPI maths, breakdowns, admin-only AI quality."""

from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utcnow
from app.db.enums import Category, EventType, Role, Severity, TicketStatus
from app.db.models import Department, TicketEvent, User
from tests.conftest import Factory, auth


@pytest.fixture
async def eng(make: Factory) -> Department:
    return await make.department("engineering", "Engineering")


@pytest.fixture
async def admin(make: Factory) -> User:
    return await make.user(Role.ADMIN, name="Meena")


@pytest.fixture
async def agent(make: Factory, eng: Department) -> User:
    return await make.user(Role.AGENT, eng, name="Ravi")


async def test_summary_counts_open_resolved_and_auto(
    client: AsyncClient, make: Factory, admin: User, eng: Department
) -> None:
    r = await make.user(Role.REQUESTER)
    now = utcnow()
    await make.ticket(r, department=eng, status=TicketStatus.NEW)
    await make.ticket(r, department=eng, status=TicketStatus.IN_PROGRESS)
    await make.ticket(r, status=TicketStatus.RESOLVED, resolved_at=now - timedelta(hours=1))
    await make.ticket(r, status=TicketStatus.AUTO_RESOLVED, resolved_at=now - timedelta(hours=2))

    body = (await client.get("/api/v1/analytics/summary", headers=auth(admin))).json()

    assert body["open_tickets"] == 2
    assert body["resolved_this_period"] == 2
    assert body["auto_resolved"] == 1
    assert body["auto_resolution_rate"] == 0.5


async def test_summary_counts_sla_breaches(client: AsyncClient, make: Factory, admin: User) -> None:
    r = await make.user(Role.REQUESTER)
    await make.ticket(r, status=TicketStatus.NEW, resolve_due_at=utcnow() - timedelta(hours=1))
    await make.ticket(r, status=TicketStatus.NEW, resolve_due_at=utcnow() + timedelta(hours=1))

    body = (await client.get("/api/v1/analytics/summary", headers=auth(admin))).json()

    assert body["sla_breaches"] == 1


async def test_agent_summary_is_scoped_to_their_department(
    client: AsyncClient, make: Factory, agent: User, eng: Department
) -> None:
    r = await make.user(Role.REQUESTER)
    it = await make.department("it", "IT")
    await make.ticket(r, department=eng, status=TicketStatus.NEW)
    await make.ticket(r, department=it, status=TicketStatus.NEW)

    body = (await client.get("/api/v1/analytics/summary", headers=auth(agent))).json()

    assert body["open_tickets"] == 1  # only Engineering


async def test_reopen_rate_is_reopened_over_auto_resolved(
    client: AsyncClient, make: Factory, admin: User, db: AsyncSession
) -> None:
    r = await make.user(Role.REQUESTER)
    t = await make.ticket(r, status=TicketStatus.NEW)
    db.add_all(
        [
            TicketEvent(ticket_id=t.id, type=EventType.STATUS_CHANGED, to_value="AUTO_RESOLVED"),
            TicketEvent(ticket_id=t.id, type=EventType.STATUS_CHANGED, to_value="AUTO_RESOLVED"),
            TicketEvent(ticket_id=t.id, type=EventType.REOPENED, from_value="AUTO_RESOLVED"),
        ]
    )
    await db.commit()

    body = (await client.get("/api/v1/analytics/summary", headers=auth(admin))).json()

    assert body["reopen_rate"] == 0.5


async def test_volume_fills_every_day_in_range(
    client: AsyncClient, make: Factory, admin: User
) -> None:
    r = await make.user(Role.REQUESTER)
    await make.ticket(r, status=TicketStatus.NEW)

    rows = (await client.get("/api/v1/analytics/volume", headers=auth(admin))).json()

    assert len(rows) == 31  # default range is 30 days inclusive
    assert rows[-1]["created"] == 1  # today
    assert all(row["created"] == 0 for row in rows[:-1])


@pytest.mark.parametrize(
    ("by", "expected_key"),
    [("category", "ACCESS"), ("severity", "HIGH"), ("department", "engineering")],
)
async def test_breakdown_groups_by(
    client: AsyncClient,
    make: Factory,
    admin: User,
    eng: Department,
    by: str,
    expected_key: str,
) -> None:
    r = await make.user(Role.REQUESTER)
    await make.ticket(
        r, department=eng, category=Category.ACCESS, severity=Severity.HIGH, status=TicketStatus.NEW
    )

    rows = (await client.get(f"/api/v1/analytics/breakdown?by={by}", headers=auth(admin))).json()

    assert any(row["key"] == expected_key and row["count"] == 1 for row in rows)


async def test_ai_quality_is_admin_only(
    client: AsyncClient, make: Factory, admin: User, agent: User, db: AsyncSession
) -> None:
    r = await make.user(Role.REQUESTER)
    await make.ticket(r, status=TicketStatus.AUTO_RESOLVED, ai_confidence=92)
    await make.ticket(r, status=TicketStatus.NEW, ai_confidence=70)

    forbidden = await client.get("/api/v1/analytics/ai-quality", headers=auth(agent))
    body = (await client.get("/api/v1/analytics/ai-quality", headers=auth(admin))).json()

    assert forbidden.status_code == 403
    assert body["auto_resolved"] == 1
    assert sum(b["count"] for b in body["confidence_histogram"]) == 2
    assert next(b["count"] for b in body["confidence_histogram"] if b["bucket"] == "85-100") == 1


async def test_analytics_requires_staff(client: AsyncClient, make: Factory) -> None:
    requester = await make.user(Role.REQUESTER)

    assert (
        await client.get("/api/v1/analytics/summary", headers=auth(requester))
    ).status_code == 403


async def test_bad_date_range_is_rejected(client: AsyncClient, admin: User) -> None:
    r = await client.get(
        "/api/v1/analytics/summary?from=2026-10-30&to=2026-01-01", headers=auth(admin)
    )

    assert r.status_code == 400
    assert r.json()["error"]["code"] == "INVALID_RANGE"


async def test_date_range_is_capped(client: AsyncClient, admin: User) -> None:
    r = await client.get(
        "/api/v1/analytics/volume?from=0001-01-01&to=2026-10-31", headers=auth(admin)
    )

    assert r.status_code == 400
    assert r.json()["error"]["code"] == "INVALID_RANGE"


async def test_agent_without_department_sees_no_tickets(client: AsyncClient, make: Factory) -> None:
    loner = await make.user(Role.AGENT)  # no department
    await make.ticket(await make.user(Role.REQUESTER), status=TicketStatus.NEW)

    body = (await client.get("/api/v1/analytics/summary", headers=auth(loner))).json()

    assert body["open_tickets"] == 0
