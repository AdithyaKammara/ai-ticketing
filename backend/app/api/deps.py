from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import AppError
from app.core.rate_limit import RateLimiter
from app.core.security import decode_access_token
from app.db.enums import Role
from app.db.models import User
from app.workers.queue import TriageQueue

bearer = HTTPBearer(auto_error=False)


def get_settings_dep(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.sessionmaker() as session:
        yield session


def get_rate_limiter(request: Request) -> RateLimiter:
    return RateLimiter(request.app.state.redis)


def get_triage_queue(request: Request) -> TriageQueue:
    queue: TriageQueue = request.app.state.triage_queue
    return queue


SettingsDep = Annotated[Settings, Depends(get_settings_dep)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]
LimiterDep = Annotated[RateLimiter, Depends(get_rate_limiter)]
QueueDep = Annotated[TriageQueue, Depends(get_triage_queue)]


async def get_current_user(
    session: SessionDep,
    settings: SettingsDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> User:
    if credentials is None:
        raise AppError(401, "UNAUTHENTICATED", "Sign in to continue")
    user_id = decode_access_token(credentials.credentials, settings.jwt_secret.get_secret_value())
    user = await session.get(User, user_id) if user_id else None
    if user is None or not user.is_active:
        raise AppError(401, "UNAUTHENTICATED", "Your session has expired; sign in again")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: Role) -> Callable[[User], Awaitable[User]]:
    async def check(user: CurrentUser) -> User:
        if user.role not in roles:
            raise AppError(403, "FORBIDDEN", "You do not have access to this action")
        return user

    return check


StaffUser = Annotated[User, Depends(require_roles(Role.AGENT, Role.ADMIN))]
AdminUser = Annotated[User, Depends(require_roles(Role.ADMIN))]
