"""Agent selection (FR-4).

score = 3 x matched skills - 1 x open tickets - 2 if BUSY. Agents on leave or inactive are
never candidates. Open load is counted with a query at routing time, never stored.
"""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import OPEN_STATUSES, Availability, Role
from app.db.models import Skill, Ticket, User, user_skills

SKILL_WEIGHT = 3
LOAD_WEIGHT = 1
BUSY_PENALTY = 2


@dataclass(frozen=True)
class Candidate:
    user_id: UUID
    name: str
    skills: frozenset[str]
    open_tickets: int
    availability: Availability


def score(candidate: Candidate, wanted_skills: set[str]) -> int:
    matched = len(candidate.skills & wanted_skills)
    busy = BUSY_PENALTY if candidate.availability is Availability.BUSY else 0
    return SKILL_WEIGHT * matched - LOAD_WEIGHT * candidate.open_tickets - busy


def pick_assignee(candidates: list[Candidate], wanted_skills: set[str]) -> Candidate | None:
    """Best score wins; ties go to the lighter load, then name, so routing is deterministic."""
    eligible = [c for c in candidates if c.availability is not Availability.ON_LEAVE]
    if not eligible:
        return None
    return min(
        eligible,
        key=lambda c: (-score(c, wanted_skills), c.open_tickets, c.name, str(c.user_id)),
    )


def open_load_query() -> Select[UUID | None, int]:
    """Open tickets per assignee; the only definition of 'load' in the system."""
    return (
        select(Ticket.assignee_id, func.count().label("open_tickets"))
        .where(Ticket.status.in_(OPEN_STATUSES), Ticket.assignee_id.is_not(None))
        .group_by(Ticket.assignee_id)
    )


async def open_load(session: AsyncSession, user_id: UUID) -> int:
    result = await session.scalar(
        select(func.count())
        .select_from(Ticket)
        .where(Ticket.assignee_id == user_id, Ticket.status.in_(OPEN_STATUSES))
    )
    return int(result or 0)


async def load_candidates(session: AsyncSession, department_id: UUID) -> list[Candidate]:
    load = open_load_query().subquery()
    rows = await session.execute(
        select(User.id, User.full_name, User.availability, load.c.open_tickets)
        .outerjoin(load, load.c.assignee_id == User.id)
        .where(
            User.department_id == department_id,
            User.role == Role.AGENT,
            User.is_active.is_(True),
            User.availability != Availability.ON_LEAVE,
        )
    )
    agents = rows.all()
    if not agents:
        return []

    skill_rows = await session.execute(
        select(user_skills.c.user_id, Skill.slug)
        .join(Skill, Skill.id == user_skills.c.skill_id)
        .where(user_skills.c.user_id.in_([a.id for a in agents]))
    )
    skills: dict[UUID, set[str]] = {}
    for user_id, slug in skill_rows:
        skills.setdefault(user_id, set()).add(slug)

    return [
        Candidate(
            user_id=a.id,
            name=a.full_name,
            skills=frozenset(skills.get(a.id, set())),
            open_tickets=int(a.open_tickets or 0),
            availability=a.availability,
        )
        for a in agents
    ]


async def choose_assignee(
    session: AsyncSession, department_id: UUID, wanted_skills: set[str]
) -> UUID | None:
    best = pick_assignee(await load_candidates(session, department_id), wanted_skills)
    return best.user_id if best else None
