"""Shared fixtures.

API tests run against real PostgreSQL and Redis: `docker compose up -d postgres redis`
locally, service containers in CI. Override with TEST_DATABASE_URL / TEST_REDIS_URL.
The LLM is never called from tests; the triage queue is replaced by FakeQueue.
"""

import asyncio
import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from uuid import UUID

import asyncpg
import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.security import create_access_token, hash_password
from app.db.base import Base
from app.db.enums import Availability, Category, Role, Severity, TicketStatus, TriageStatus
from app.db.models import CategoryRoute, Department, Skill, Ticket, User
from app.main import create_app

BACKEND_DIR = Path(__file__).resolve().parents[1]
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql://ticketing:ticketing@localhost:5432/ticketing_test"
)
TEST_REDIS_URL = os.environ.get("TEST_REDIS_URL", "redis://localhost:6379/15")
JWT_SECRET = "test-secret-that-is-at-least-32-characters"
PASSWORD = "correct-horse-battery"

# Nothing listens on port 1, so dependency checks fail fast and deterministically.
UNREACHABLE_DB = "postgresql://ticketing:ticketing@127.0.0.1:1/ticketing"
UNREACHABLE_REDIS = "redis://127.0.0.1:1/0"


def make_settings(database_url: str, redis_url: str) -> Settings:
    return Settings(
        _env_file=None,
        environment="test",
        database_url=database_url,
        redis_url=redis_url,
        jwt_secret=JWT_SECRET,
        cookie_secure=False,
    )


def alembic_config(database_url: str) -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url)
    config.attributes["configure_logger"] = False
    return config


async def recreate_database(url: str) -> None:
    base, name = url.rsplit("/", 1)
    conn = await asyncpg.connect(f"{base}/postgres")
    try:
        await conn.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        await conn.execute(f'CREATE DATABASE "{name}"')
    finally:
        await conn.close()


# ------------------------------------------------------------------ offline app (no services)


@pytest.fixture
def offline_client() -> Iterator[TestClient]:
    app = create_app(make_settings(UNREACHABLE_DB, UNREACHABLE_REDIS))
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


# ------------------------------------------------------------------ database-backed app


@pytest.fixture(scope="session")
def migrated_database() -> str:
    asyncio.run(recreate_database(TEST_DATABASE_URL))
    command.upgrade(alembic_config(TEST_DATABASE_URL), "head")
    return TEST_DATABASE_URL


class FakeQueue:
    def __init__(self) -> None:
        self.enqueued: list[UUID] = []
        self.fail = False

    async def enqueue_triage(self, ticket_id: UUID) -> None:
        if self.fail:
            raise ConnectionError("redis is down")
        self.enqueued.append(ticket_id)


@pytest.fixture
async def app(migrated_database: str) -> AsyncIterator[FastAPI]:
    app = create_app(make_settings(migrated_database, TEST_REDIS_URL))
    async with app.router.lifespan_context(app):
        async with app.state.sessionmaker() as session:
            tables = ", ".join(t.name for t in reversed(Base.metadata.sorted_tables))
            await session.execute(text(f"TRUNCATE {tables} CASCADE"))
            await session.commit()
        redis: Redis = app.state.redis
        await redis.flushdb()
        app.state.triage_queue = FakeQueue()
        yield app


@pytest.fixture
def queue(app: FastAPI) -> FakeQueue:
    fake: FakeQueue = app.state.triage_queue
    return fake


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
async def db(app: FastAPI) -> AsyncIterator[AsyncSession]:
    async with app.state.sessionmaker() as session:
        yield session


# ------------------------------------------------------------------ factories


class Factory:
    """Builds rows directly in the database; API behaviour is then tested over HTTP."""

    _password_hash = hash_password(PASSWORD)

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.counter = 0

    def _next(self) -> int:
        self.counter += 1
        return self.counter

    async def department(self, slug: str = "engineering", name: str | None = None) -> Department:
        department = Department(slug=slug, name=name or slug.title())
        self.session.add(department)
        await self.session.commit()
        return department

    async def skill(self, slug: str) -> Skill:
        skill = Skill(slug=slug, name=slug)
        self.session.add(skill)
        await self.session.commit()
        return skill

    async def route(
        self, category: Category, department: Department, skills: list[str] | None = None
    ) -> CategoryRoute:
        route = CategoryRoute(
            category=category,
            department_id=department.id,
            default_skills=skills or [],
            auto_resolve_allowed=False,
        )
        self.session.add(route)
        await self.session.commit()
        return route

    async def user(
        self,
        role: Role = Role.REQUESTER,
        department: Department | None = None,
        *,
        name: str | None = None,
        email: str | None = None,
        skills: list[Skill] | None = None,
        availability: Availability = Availability.AVAILABLE,
        is_active: bool = True,
    ) -> User:
        n = self._next()
        user = User(
            email=email or f"user{n}@acme.example",
            full_name=name or f"{role.value.title()} {n}",
            password_hash=self._password_hash,
            role=role,
            department_id=department.id if department else None,
            availability=availability,
            is_active=is_active,
            skills=skills or [],
        )
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def ticket(
        self,
        requester: User,
        *,
        status: TicketStatus = TicketStatus.NEW,
        department: Department | None = None,
        assignee: User | None = None,
        category: Category | None = None,
        severity: Severity | None = None,
        title: str | None = None,
        **fields: object,
    ) -> Ticket:
        ticket = Ticket(
            title=title or f"Ticket number {self._next()}",
            description="Something is not working as expected today.",
            requester_id=requester.id,
            status=status,
            triage_status=TriageStatus.DONE,
            department_id=department.id if department else None,
            assignee_id=assignee.id if assignee else None,
            category=category,
            severity=severity,
            **fields,
        )
        self.session.add(ticket)
        await self.session.commit()
        await self.session.refresh(ticket)
        return ticket


@pytest.fixture
def make(db: AsyncSession) -> Factory:
    return Factory(db)


def auth(user: User) -> dict[str, str]:
    token = create_access_token(user.id, user.role, JWT_SECRET, ttl_minutes=15)
    return {"Authorization": f"Bearer {token}"}
