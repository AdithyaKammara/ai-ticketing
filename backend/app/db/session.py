from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def async_database_url(url: str) -> str:
    """Point a plain postgres URL at the asyncpg driver.

    Hosted URLs (Neon) carry libpq options asyncpg rejects: `sslmode` becomes asyncpg's
    `ssl`, and `channel_binding` is dropped.
    """
    for prefix in ("postgresql://", "postgres://"):
        if url.startswith(prefix):
            url = "postgresql+asyncpg://" + url.removeprefix(prefix)
            break
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query))
    query.pop("channel_binding", None)
    if "sslmode" in query:
        query["ssl"] = query.pop("sslmode")
    return urlunsplit(parts._replace(query=urlencode(query)))


def create_engine(url: str) -> AsyncEngine:
    return create_async_engine(
        async_database_url(url),
        pool_pre_ping=True,
        # Serverless Postgres (Neon) can take a few seconds to wake from idle.
        connect_args={"timeout": 10},
    )


def create_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)
