from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utcnow
from app.core.config import Settings
from app.core.errors import AppError
from app.core.rate_limit import Limit, RateLimiter
from app.core.security import (
    create_access_token,
    hash_password,
    hash_refresh_token,
    new_refresh_token,
    verify_password,
)
from app.db.enums import Role
from app.db.models import RefreshToken, User


@dataclass(frozen=True)
class IssuedSession:
    user: User
    access_token: str
    refresh_token: str


def login_limit(settings: Settings) -> Limit:
    return Limit("login-failures", settings.login_max_failures, settings.login_lockout_seconds)


async def find_user_by_email(session: AsyncSession, email: str) -> User | None:
    result: User | None = await session.scalar(
        select(User).where(func.lower(User.email) == email.lower())
    )
    return result


async def register(session: AsyncSession, email: str, password: str, full_name: str) -> User:
    user = User(
        email=email.lower(),
        password_hash=hash_password(password),
        full_name=full_name,
        role=Role.REQUESTER,
    )
    session.add(user)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise AppError(409, "EMAIL_TAKEN", "An account with this email already exists") from exc
    await session.refresh(user)
    return user


async def login(
    session: AsyncSession,
    limiter: RateLimiter,
    settings: Settings,
    email: str,
    password: str,
) -> IssuedSession:
    limit = login_limit(settings)
    if await limiter.is_blocked(limit, email):
        raise AppError(
            429, "RATE_LIMITED", "Too many failed sign-in attempts. Try again in 15 minutes."
        )

    user = await find_user_by_email(session, email)
    valid = verify_password(password, user.password_hash if user else None)
    if user is None or not valid or not user.is_active:
        await limiter.hit(limit, email)
        raise AppError(401, "INVALID_CREDENTIALS", "Email or password is incorrect")

    await limiter.reset(limit, email)
    return await _issue_session(session, settings, user)


async def refresh(
    session: AsyncSession, settings: Settings, raw_token: str | None
) -> IssuedSession:
    """Rotate a refresh token. Presenting a revoked token revokes the user's whole family."""
    if not raw_token:
        raise AppError(401, "UNAUTHENTICATED", "Sign in to continue")

    stored = await session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(raw_token))
    )
    now = utcnow()
    if stored is None or stored.expires_at <= now:
        raise AppError(401, "UNAUTHENTICATED", "Your session has expired; sign in again")

    if stored.revoked_at is not None:
        # Reuse of a rotated token means it was stolen; end every session for this user.
        await revoke_all(session, stored.user_id)
        await session.commit()
        raise AppError(401, "UNAUTHENTICATED", "Your session has expired; sign in again")

    user = await session.get(User, stored.user_id)
    if user is None or not user.is_active:
        raise AppError(401, "UNAUTHENTICATED", "Your session has expired; sign in again")

    issued = await _issue_session(session, settings, user, replacing=stored)
    return issued


async def logout(session: AsyncSession, raw_token: str | None) -> None:
    if not raw_token:
        return
    await session.execute(
        update(RefreshToken)
        .where(
            RefreshToken.token_hash == hash_refresh_token(raw_token),
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=utcnow())
    )
    await session.commit()


async def revoke_all(session: AsyncSession, user_id: UUID) -> None:
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )


async def _issue_session(
    session: AsyncSession,
    settings: Settings,
    user: User,
    replacing: RefreshToken | None = None,
) -> IssuedSession:
    raw = new_refresh_token()
    token = RefreshToken(
        user_id=user.id,
        token_hash=hash_refresh_token(raw),
        expires_at=utcnow() + timedelta(days=settings.refresh_token_ttl_days),
    )
    session.add(token)
    await session.flush()
    if replacing is not None:
        replacing.revoked_at = utcnow()
        replacing.replaced_by = token.id
    await session.commit()

    access = create_access_token(
        user.id,
        user.role,
        settings.jwt_secret.get_secret_value(),
        settings.access_token_ttl_minutes,
    )
    return IssuedSession(user=user, access_token=access, refresh_token=raw)
