from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def async_database_url(url: str) -> str:
    """Point a plain postgres URL at the asyncpg driver."""
    for prefix in ("postgresql://", "postgres://"):
        if url.startswith(prefix):
            return "postgresql+asyncpg://" + url.removeprefix(prefix)
    return url


def create_engine(url: str) -> AsyncEngine:
    return create_async_engine(
        async_database_url(url),
        pool_pre_ping=True,
        connect_args={"timeout": 2},
    )


def create_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)
