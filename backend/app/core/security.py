import hashlib
import secrets
from datetime import timedelta
from typing import Any
from uuid import UUID

import jwt
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

from app.core.clock import utcnow
from app.db.enums import Role

JWT_ALGORITHM = "HS256"
REFRESH_COOKIE = "refresh_token"

_password_hash = PasswordHash((Argon2Hasher(),))
# Verifying against this when the email is unknown keeps login timing the same either way.
_DUMMY_HASH = _password_hash.hash("not-a-real-password")


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    if password_hash is None:
        _password_hash.verify(password, _DUMMY_HASH)
        return False
    return _password_hash.verify(password, password_hash)


def create_access_token(user_id: UUID, role: Role, secret: str, ttl_minutes: int) -> str:
    now = utcnow()
    claims: dict[str, Any] = {
        "sub": str(user_id),
        "role": role.value,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=ttl_minutes),
    }
    return jwt.encode(claims, secret, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str, secret: str) -> UUID | None:
    """Return the user id for a valid, unexpired access token, else None."""
    try:
        claims = jwt.decode(
            token, secret, algorithms=[JWT_ALGORITHM], options={"require": ["exp", "sub"]}
        )
        if claims.get("type") != "access":
            return None
        return UUID(claims["sub"])
    except (jwt.PyJWTError, ValueError):
        return None


def new_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
