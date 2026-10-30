from typing import Annotated

from fastapi import APIRouter, Cookie, Response, status

from app.api.deps import CurrentUser, LimiterDep, SessionDep, SettingsDep
from app.core.config import Settings
from app.core.errors import AppError
from app.core.security import REFRESH_COOKIE
from app.schemas.auth import LoginIn, MeOut, RegisterIn, TokenOut
from app.services import auth_service
from app.services.auth_service import IssuedSession

router = APIRouter(prefix="/auth", tags=["auth"])

COOKIE_PATH = "/api/v1/auth"
RefreshCookie = Annotated[str | None, Cookie(alias=REFRESH_COOKIE)]


def _token_response(response: Response, settings: Settings, issued: IssuedSession) -> TokenOut:
    response.set_cookie(
        REFRESH_COOKIE,
        issued.refresh_token,
        max_age=settings.refresh_token_ttl_days * 24 * 3600,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path=COOKIE_PATH,
    )
    return TokenOut(
        access_token=issued.access_token,
        expires_in=settings.access_token_ttl_minutes * 60,
        user=MeOut.model_validate(issued.user),
    )


@router.post("/register", response_model=MeOut, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterIn, session: SessionDep, settings: SettingsDep) -> MeOut:
    if not settings.allow_registration:
        raise AppError(403, "REGISTRATION_CLOSED", "Sign-up is closed; use a demo account")
    user = await auth_service.register(session, body.email, body.password, body.full_name)
    return MeOut.model_validate(user)


@router.post("/login", response_model=TokenOut)
async def login(
    body: LoginIn,
    response: Response,
    session: SessionDep,
    limiter: LimiterDep,
    settings: SettingsDep,
) -> TokenOut:
    issued = await auth_service.login(session, limiter, settings, body.email, body.password)
    return _token_response(response, settings, issued)


@router.post("/refresh", response_model=TokenOut)
async def refresh(
    response: Response,
    session: SessionDep,
    settings: SettingsDep,
    refresh_token: RefreshCookie = None,
) -> TokenOut:
    issued = await auth_service.refresh(session, settings, refresh_token)
    return _token_response(response, settings, issued)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    session: SessionDep,
    settings: SettingsDep,
    refresh_token: RefreshCookie = None,
) -> None:
    await auth_service.logout(session, refresh_token)
    response.delete_cookie(
        REFRESH_COOKIE,
        path=COOKIE_PATH,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
    )


@router.get("/me", response_model=MeOut)
async def me(user: CurrentUser) -> MeOut:
    return MeOut.model_validate(user)
