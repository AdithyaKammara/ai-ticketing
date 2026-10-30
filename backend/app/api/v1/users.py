from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, status

from app.api.deps import AdminUser, CurrentUser, SessionDep, StaffUser
from app.db.enums import Role
from app.db.models import User
from app.schemas.users import UserCreateIn, UserOut, UserUpdateIn
from app.services import routing, user_service

router = APIRouter(prefix="/users", tags=["users"])


def user_out(user: User, open_tickets: int) -> UserOut:
    out = UserOut.model_validate(user)
    out.open_tickets = open_tickets
    return out


@router.get("", response_model=list[UserOut])
async def list_users(
    viewer: StaffUser,
    session: SessionDep,
    role: Role | None = None,
    department_id: UUID | None = None,
    q: Annotated[str | None, Query(max_length=120)] = None,
    include_inactive: bool = False,
) -> list[UserOut]:
    rows = await user_service.list_users(session, viewer, role, department_id, q, include_inactive)
    return [user_out(user, count) for user, count in rows]


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(body: UserCreateIn, _: AdminUser, session: SessionDep) -> UserOut:
    user = await user_service.create_user(session, body)
    return user_out(user, 0)


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: UUID, body: UserUpdateIn, actor: CurrentUser, session: SessionDep
) -> UserOut:
    user = await user_service.update_user(session, actor, user_id, body)
    return user_out(user, await routing.open_load(session, user.id))


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_user(user_id: UUID, actor: AdminUser, session: SessionDep) -> None:
    await user_service.deactivate_user(session, actor, user_id)
