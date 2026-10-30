from fastapi import FastAPI
from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import REFRESH_COOKIE, create_access_token
from app.db.enums import Role
from app.db.models import RefreshToken
from tests.conftest import JWT_SECRET, PASSWORD, Factory, auth

REGISTER = {"email": "Priya@Acme.example", "password": "a-long-password", "full_name": "Priya"}


async def login(client: AsyncClient, email: str, password: str = PASSWORD) -> str:
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return str(response.cookies[REFRESH_COOKIE])


async def post_with_cookie(client: AsyncClient, path: str, token: str) -> Response:
    client.cookies.clear()
    client.cookies.set(REFRESH_COOKIE, token)
    return await client.post(path)


async def test_register_creates_a_requester(client: AsyncClient) -> None:
    response = await client.post("/api/v1/auth/register", json=REGISTER)

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "priya@acme.example"
    assert body["role"] == "REQUESTER"
    assert "password_hash" not in body


async def test_register_duplicate_email_returns_409_case_insensitively(
    client: AsyncClient,
) -> None:
    await client.post("/api/v1/auth/register", json=REGISTER)

    response = await client.post(
        "/api/v1/auth/register", json={**REGISTER, "email": "PRIYA@acme.example"}
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "EMAIL_TAKEN"


async def test_register_validates_password_length(client: AsyncClient) -> None:
    response = await client.post("/api/v1/auth/register", json={**REGISTER, "password": "short"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_register_can_be_closed(app: FastAPI, client: AsyncClient) -> None:
    app.state.settings = app.state.settings.model_copy(update={"allow_registration": False})

    response = await client.post("/api/v1/auth/register", json=REGISTER)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "REGISTRATION_CLOSED"


async def test_login_returns_access_token_and_httponly_refresh_cookie(
    client: AsyncClient, make: Factory
) -> None:
    user = await make.user(Role.AGENT, await make.department())

    response = await client.post(
        "/api/v1/auth/login", json={"email": user.email.upper(), "password": PASSWORD}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 900
    assert body["user"]["role"] == "AGENT"
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie
    assert "Path=/api/v1/auth" in cookie

    me = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"}
    )
    assert me.json()["id"] == str(user.id)


async def test_login_with_wrong_password_returns_401(client: AsyncClient, make: Factory) -> None:
    user = await make.user()

    response = await client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": "wrong-password"}
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


async def test_login_for_unknown_or_inactive_user_returns_401(
    client: AsyncClient, make: Factory
) -> None:
    inactive = await make.user(is_active=False)

    for email in ("nobody@acme.example", inactive.email):
        response = await client.post(
            "/api/v1/auth/login", json={"email": email, "password": PASSWORD}
        )
        assert response.status_code == 401


async def test_fr1_five_failed_logins_lock_the_email_for_fifteen_minutes(
    client: AsyncClient, make: Factory
) -> None:
    user = await make.user()
    for _ in range(5):
        await client.post("/api/v1/auth/login", json={"email": user.email, "password": "nope"})

    # Even the right password is refused while locked.
    response = await client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": PASSWORD}
    )

    assert response.status_code == 429
    assert response.json()["error"]["code"] == "RATE_LIMITED"


async def test_successful_login_clears_failed_attempts(client: AsyncClient, make: Factory) -> None:
    user = await make.user()
    for _ in range(4):
        await client.post("/api/v1/auth/login", json={"email": user.email, "password": "nope"})
    await login(client, user.email)

    for _ in range(4):
        await client.post("/api/v1/auth/login", json={"email": user.email, "password": "nope"})
    await login(client, user.email)


async def test_refresh_rotates_the_token(client: AsyncClient, make: Factory) -> None:
    user = await make.user()
    first = await login(client, user.email)

    response = await post_with_cookie(client, "/api/v1/auth/refresh", first)

    assert response.status_code == 200
    assert response.json()["access_token"]
    assert response.cookies[REFRESH_COOKIE] != first


async def test_reusing_a_rotated_refresh_token_revokes_the_whole_family(
    client: AsyncClient, make: Factory, db: AsyncSession
) -> None:
    user = await make.user()
    first = await login(client, user.email)
    rotated = await post_with_cookie(client, "/api/v1/auth/refresh", first)
    second = rotated.cookies[REFRESH_COOKIE]

    replay = await post_with_cookie(client, "/api/v1/auth/refresh", first)
    after_replay = await post_with_cookie(client, "/api/v1/auth/refresh", second)

    assert replay.status_code == 401
    assert after_replay.status_code == 401
    tokens = (await db.scalars(select(RefreshToken).where(RefreshToken.user_id == user.id))).all()
    assert all(t.revoked_at is not None for t in tokens)


async def test_refresh_without_or_with_unknown_cookie_returns_401(client: AsyncClient) -> None:
    assert (await client.post("/api/v1/auth/refresh")).status_code == 401
    unknown = await post_with_cookie(client, "/api/v1/auth/refresh", "made-up")
    assert unknown.status_code == 401


async def test_logout_revokes_the_refresh_token(client: AsyncClient, make: Factory) -> None:
    user = await make.user()
    token = await login(client, user.email)

    response = await post_with_cookie(client, "/api/v1/auth/logout", token)
    refresh = await post_with_cookie(client, "/api/v1/auth/refresh", token)

    assert response.status_code == 204
    assert refresh.status_code == 401


async def test_logout_without_cookie_is_a_no_op(client: AsyncClient) -> None:
    assert (await client.post("/api/v1/auth/logout")).status_code == 204


async def test_me_requires_a_valid_token(client: AsyncClient, make: Factory) -> None:
    user = await make.user()
    expired = create_access_token(user.id, user.role, JWT_SECRET, ttl_minutes=-1)

    missing = await client.get("/api/v1/auth/me")
    stale = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {expired}"})

    assert missing.status_code == 401
    assert stale.status_code == 401
    assert missing.json()["error"]["code"] == "UNAUTHENTICATED"


async def test_deactivated_user_token_stops_working(
    client: AsyncClient, make: Factory, db: AsyncSession
) -> None:
    user = await make.user()
    headers = auth(user)
    user.is_active = False
    await db.commit()

    assert (await client.get("/api/v1/auth/me", headers=headers)).status_code == 401
