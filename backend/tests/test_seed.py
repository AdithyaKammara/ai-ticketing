from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import seed
from app.db.enums import Availability, Role, TicketStatus
from app.db.models import Department, Ticket, User


async def test_seed_creates_the_demo_world_once(db: AsyncSession, client: AsyncClient) -> None:
    assert await seed.seed(db) is True
    assert await seed.seed(db) is False  # idempotent: a second run changes nothing

    async def count(model: type, *where: object) -> int:
        return int(
            await db.scalar(select(func.count()).select_from(model).where(*where))  # type: ignore[arg-type]
            or 0
        )

    assert await count(Department) == 6
    assert await count(User, User.role == Role.AGENT) == 12
    assert await count(Ticket) == 40
    assert await count(Ticket, Ticket.status == TicketStatus.AUTO_RESOLVED) > 0

    on_leave = await db.scalars(select(User.id).where(User.availability == Availability.ON_LEAVE))
    assigned_to_on_leave = await count(Ticket, Ticket.assignee_id.in_(list(on_leave)))
    assert assigned_to_on_leave == 0

    for person in (seed.DEMO_REQUESTER, seed.DEMO_AGENT, seed.DEMO_ADMIN):
        response = await client.post(
            "/api/v1/auth/login", json={"email": person.email, "password": seed.DEMO_PASSWORD}
        )
        assert response.status_code == 200
        assert response.json()["user"]["role"] == person.role.value


async def test_seed_assignments_are_deterministic(db: AsyncSession) -> None:
    async def snapshot() -> list[tuple[str, str | None]]:
        rows = await db.execute(
            select(Ticket.title, User.email)
            .outerjoin(User, User.id == Ticket.assignee_id)
            .order_by(Ticket.number)
        )
        return [(title, email) for title, email in rows]

    await seed.seed(db)
    first = await snapshot()
    await seed.reset(db)
    await seed.seed(db)

    assert await snapshot() == first
