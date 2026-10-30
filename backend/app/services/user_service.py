from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.security import hash_password
from app.db.enums import Availability, Role
from app.db.models import Department, Skill, User
from app.schemas.users import UserCreateIn, UserUpdateIn
from app.services import auth_service, routing, ticket_service
from app.services.skills import normalize_skills

MAX_DIRECTORY_SIZE = 500


async def resolve_skills(session: AsyncSession, names: list[str]) -> list[Skill]:
    """Map names to existing skill tags; unknown tags are rejected rather than invented."""
    slugs = normalize_skills(names)
    if not slugs:
        return []
    skills = list(await session.scalars(select(Skill).where(Skill.slug.in_(slugs))))
    unknown = slugs - {s.slug for s in skills}
    if unknown:
        raise AppError(422, "UNKNOWN_SKILL", "Unknown skill tags", {"skills": sorted(unknown)})
    return skills


async def ensure_department(session: AsyncSession, department_id: UUID | None) -> None:
    if department_id is not None and await session.get(Department, department_id) is None:
        raise AppError(422, "UNKNOWN_DEPARTMENT", "Department not found")


async def list_users(
    session: AsyncSession,
    viewer: User,
    role: Role | None,
    department_id: UUID | None,
    q: str | None,
    include_inactive: bool,
) -> list[tuple[User, int]]:
    load = routing.open_load_query().subquery()
    query = select(User, func.coalesce(load.c.open_tickets, 0)).outerjoin(
        load, load.c.assignee_id == User.id
    )
    if viewer.role is not Role.ADMIN:
        # Agents get a read-only staff directory, never the list of requesters.
        query = query.where(User.role.in_((Role.AGENT, Role.ADMIN)), User.is_active.is_(True))
    elif not include_inactive:
        query = query.where(User.is_active.is_(True))
    if role is not None:
        query = query.where(User.role == role)
    if department_id is not None:
        query = query.where(User.department_id == department_id)
    if q:
        pattern = f"%{q.replace('%', '').replace('_', '')}%"
        query = query.where(or_(User.full_name.ilike(pattern), User.email.ilike(pattern)))
    query = query.order_by(User.full_name, User.id).limit(MAX_DIRECTORY_SIZE)
    rows = (await session.execute(query)).unique().all()
    return [(user, int(count)) for user, count in rows]


async def create_user(session: AsyncSession, body: UserCreateIn) -> User:
    await ensure_department(session, body.department_id)
    if body.role is Role.AGENT and body.department_id is None:
        raise AppError(422, "DEPARTMENT_REQUIRED", "Agents need a department")
    user = User(
        email=body.email.lower(),
        full_name=body.full_name,
        password_hash=hash_password(body.password),
        role=body.role,
        department_id=body.department_id,
        availability=body.availability,
        skills=await resolve_skills(session, body.skills),
    )
    session.add(user)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise AppError(409, "EMAIL_TAKEN", "An account with this email already exists") from exc
    await session.refresh(user)
    return user


async def get_user(session: AsyncSession, user_id: UUID) -> User:
    user = await session.get(User, user_id)
    if user is None:
        raise AppError(404, "NOT_FOUND", "User not found")
    return user


async def update_user(
    session: AsyncSession, actor: User, user_id: UUID, body: UserUpdateIn
) -> User:
    user = await get_user(session, user_id)
    changes = body.model_dump(exclude_unset=True)

    if actor.role is not Role.ADMIN and (actor.id != user.id or set(changes) - {"availability"}):
        raise AppError(403, "FORBIDDEN", "You can only change your own availability")

    if "department_id" in changes:
        await ensure_department(session, body.department_id)
        user.department_id = body.department_id
    if body.full_name is not None:
        user.full_name = body.full_name
    if body.role is not None:
        user.role = body.role
    if body.availability is not None:
        user.availability = body.availability
    if body.skills is not None:
        user.skills = await resolve_skills(session, body.skills)
    if user.role is Role.AGENT and user.department_id is None:
        raise AppError(422, "DEPARTMENT_REQUIRED", "Agents need a department")

    await session.commit()
    await session.refresh(user)
    return user


async def deactivate_user(session: AsyncSession, actor: User, user_id: UUID) -> int:
    """Deactivate instead of delete; open tickets return to the Unassigned queue."""
    user = await get_user(session, user_id)
    if user.id == actor.id:
        raise AppError(409, "CANNOT_DEACTIVATE_SELF", "You cannot deactivate your own account")
    if not user.is_active:
        return 0
    user.is_active = False
    user.availability = Availability.ON_LEAVE
    returned = await ticket_service.unassign_open_tickets(session, actor, user)
    await auth_service.revoke_all(session, user.id)
    await session.commit()
    return returned
