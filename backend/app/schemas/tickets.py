from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, BeforeValidator, StringConstraints

from app.db.enums import (
    Category,
    EventType,
    Sentiment,
    Severity,
    TicketStatus,
    TriageStatus,
)
from app.schemas.common import DepartmentOut, Schema, UtcDatetime

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=150)]
Description = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=20, max_length=5000)
]
Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=300)]
Body = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5000)]

# Stored as an integer from a sequence; shown everywhere as TKT-1042.
TicketNumber = Annotated[str, BeforeValidator(lambda v: f"TKT-{v}" if isinstance(v, int) else v)]

TicketSort = Literal["-created_at", "created_at", "due", "severity"]


class TicketCreateIn(BaseModel):
    title: Title
    description: Description


class UserBrief(Schema):
    id: UUID
    full_name: str
    email: str


class TicketCreatedOut(Schema):
    id: UUID
    number: TicketNumber
    status: TicketStatus
    triage_status: TriageStatus
    created_at: UtcDatetime


class TicketSummaryOut(Schema):
    id: UUID
    number: TicketNumber
    title: str
    status: TicketStatus
    triage_status: TriageStatus
    category: Category | None
    severity: Severity | None
    department: DepartmentOut | None
    requester: UserBrief
    assignee: UserBrief | None
    first_response_due_at: UtcDatetime | None
    resolve_due_at: UtcDatetime | None
    created_at: UtcDatetime
    updated_at: UtcDatetime
    is_overdue: bool = False


class TicketOut(TicketSummaryOut):
    description: str
    sentiment: Sentiment | None
    ai_summary: str | None
    ai_confidence: int | None
    auto_response: str | None
    first_responded_at: UtcDatetime | None
    resolved_at: UtcDatetime | None
    closed_at: UtcDatetime | None
    feedback_given: bool = False


class StatusIn(BaseModel):
    status: TicketStatus


class AssigneeIn(BaseModel):
    assignee_id: UUID | None
    reason: Reason


class FeedbackIn(BaseModel):
    helpful: bool


class CommentIn(BaseModel):
    body: Body
    is_internal: bool = False


class EventOut(Schema):
    id: UUID
    type: EventType
    actor: UserBrief | None
    from_value: str | None
    to_value: str | None
    body: str | None
    is_internal: bool
    created_at: UtcDatetime
