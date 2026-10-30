from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    ARRAY,
    Boolean,
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    Integer,
    Sequence,
    String,
    Table,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdMixin, TimestampMixin, pg_enum
from app.db.enums import (
    Availability,
    Category,
    EventType,
    Role,
    Sentiment,
    Severity,
    TicketStatus,
    TriageStatus,
)

ROLE = pg_enum(Role, "user_role")
AVAILABILITY = pg_enum(Availability, "availability")
TICKET_STATUS = pg_enum(TicketStatus, "ticket_status")
TRIAGE_STATUS = pg_enum(TriageStatus, "triage_status")
CATEGORY = pg_enum(Category, "ticket_category")
SEVERITY = pg_enum(Severity, "severity")
SENTIMENT = pg_enum(Sentiment, "sentiment")
EVENT_TYPE = pg_enum(EventType, "event_type")

TICKET_NUMBER_SEQ = Sequence("ticket_number_seq", start=1001)

user_skills = Table(
    "user_skills",
    Base.metadata,
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("skill_id", ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True),
)


class Department(IdMixin, TimestampMixin, Base):
    __tablename__ = "departments"

    name: Mapped[str] = mapped_column(String(80))
    slug: Mapped[str] = mapped_column(String(80), unique=True)


class Skill(IdMixin, TimestampMixin, Base):
    __tablename__ = "skills"

    name: Mapped[str] = mapped_column(String(80))
    slug: Mapped[str] = mapped_column(String(80), unique=True)


class User(IdMixin, TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        Index("ix_users_department_role_active", "department_id", "role", "is_active"),
    )

    email: Mapped[str] = mapped_column(String(254))
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(120))
    role: Mapped[Role] = mapped_column(ROLE, default=Role.REQUESTER)
    department_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("departments.id", ondelete="SET NULL")
    )
    availability: Mapped[Availability] = mapped_column(AVAILABILITY, default=Availability.AVAILABLE)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    department: Mapped[Department | None] = relationship(lazy="joined")
    skills: Mapped[list[Skill]] = relationship(
        secondary=user_skills, lazy="selectin", order_by=Skill.slug
    )


Index("uq_users_email_lower", func.lower(User.email), unique=True)


class CategoryRoute(IdMixin, TimestampMixin, Base):
    """Deterministic category -> department map. Replaces v1's hard-coded DEPARTMENT_MAP."""

    __tablename__ = "category_routes"

    category: Mapped[Category] = mapped_column(CATEGORY, unique=True)
    department_id: Mapped[UUID] = mapped_column(ForeignKey("departments.id"))
    default_skills: Mapped[list[str]] = mapped_column(ARRAY(String(80)), default=list)
    auto_resolve_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    severity_floor: Mapped[Severity | None] = mapped_column(SEVERITY)

    department: Mapped[Department] = relationship(lazy="joined")


class Ticket(IdMixin, TimestampMixin, Base):
    __tablename__ = "tickets"
    __table_args__ = (
        CheckConstraint("char_length(title) BETWEEN 5 AND 150", name="title_length"),
        CheckConstraint("char_length(description) BETWEEN 20 AND 5000", name="description_length"),
        Index("ix_tickets_status_department", "status", "department_id"),
        Index("ix_tickets_assignee_status", "assignee_id", "status"),
    )

    number: Mapped[int] = mapped_column(
        Integer, TICKET_NUMBER_SEQ, server_default=TICKET_NUMBER_SEQ.next_value(), unique=True
    )
    title: Mapped[str] = mapped_column(String(150))
    description: Mapped[str] = mapped_column(Text)
    requester_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    assignee_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    department_id: Mapped[UUID | None] = mapped_column(ForeignKey("departments.id"))

    category: Mapped[Category | None] = mapped_column(CATEGORY)
    severity: Mapped[Severity | None] = mapped_column(SEVERITY)
    sentiment: Mapped[Sentiment | None] = mapped_column(SENTIMENT)
    status: Mapped[TicketStatus] = mapped_column(TICKET_STATUS, default=TicketStatus.TRIAGING)
    triage_status: Mapped[TriageStatus] = mapped_column(TRIAGE_STATUS, default=TriageStatus.PENDING)

    ai_summary: Mapped[str | None] = mapped_column(Text)
    ai_confidence: Mapped[int | None] = mapped_column(Integer)
    auto_response: Mapped[str | None] = mapped_column(Text)

    first_response_due_at: Mapped[datetime | None]
    resolve_due_at: Mapped[datetime | None]
    first_responded_at: Mapped[datetime | None]
    resolved_at: Mapped[datetime | None]
    closed_at: Mapped[datetime | None]

    requester: Mapped[User] = relationship(foreign_keys=[requester_id], lazy="joined")
    assignee: Mapped[User | None] = relationship(foreign_keys=[assignee_id], lazy="joined")
    department: Mapped[Department | None] = relationship(lazy="joined")

    @property
    def display_number(self) -> str:
        return f"TKT-{self.number}"


Index("ix_tickets_created_at_desc", Ticket.created_at.desc())


class TicketEvent(IdMixin, TimestampMixin, Base):
    __tablename__ = "ticket_events"
    __table_args__ = (Index("ix_ticket_events_ticket_created", "ticket_id", "created_at"),)

    ticket_id: Mapped[UUID] = mapped_column(ForeignKey("tickets.id", ondelete="CASCADE"))
    actor_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))  # None = system
    type: Mapped[EventType] = mapped_column(EVENT_TYPE)
    from_value: Mapped[str | None] = mapped_column(String(120))
    to_value: Mapped[str | None] = mapped_column(String(120))
    body: Mapped[str | None] = mapped_column(Text)
    is_internal: Mapped[bool] = mapped_column(Boolean, default=False)

    actor: Mapped[User | None] = relationship(lazy="joined")


class AiTriageLog(IdMixin, TimestampMixin, Base):
    __tablename__ = "ai_triage_logs"

    ticket_id: Mapped[UUID] = mapped_column(
        ForeignKey("tickets.id", ondelete="CASCADE"), index=True
    )
    provider: Mapped[str] = mapped_column(String(40))
    model: Mapped[str] = mapped_column(String(80))
    prompt_version: Mapped[str] = mapped_column(String(20))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    raw_output: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    parsed: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(Text)
    guardrail_decision: Mapped[str | None] = mapped_column(String(40))


class RefreshToken(IdMixin, TimestampMixin, Base):
    """Only the SHA-256 of each token is stored; the raw value lives in the user's cookie."""

    __tablename__ = "refresh_tokens"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime]
    revoked_at: Mapped[datetime | None]
    replaced_by: Mapped[UUID | None] = mapped_column(ForeignKey("refresh_tokens.id"))
