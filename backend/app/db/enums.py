from enum import StrEnum


class Role(StrEnum):
    REQUESTER = "REQUESTER"
    AGENT = "AGENT"
    ADMIN = "ADMIN"


class Availability(StrEnum):
    AVAILABLE = "AVAILABLE"
    BUSY = "BUSY"
    ON_LEAVE = "ON_LEAVE"


class TicketStatus(StrEnum):
    TRIAGING = "TRIAGING"
    NEW = "NEW"
    IN_PROGRESS = "IN_PROGRESS"
    WAITING_ON_REQUESTER = "WAITING_ON_REQUESTER"
    RESOLVED = "RESOLVED"
    AUTO_RESOLVED = "AUTO_RESOLVED"
    CLOSED = "CLOSED"


OPEN_STATUSES = frozenset(
    {TicketStatus.NEW, TicketStatus.IN_PROGRESS, TicketStatus.WAITING_ON_REQUESTER}
)
DONE_STATUSES = frozenset({TicketStatus.RESOLVED, TicketStatus.AUTO_RESOLVED, TicketStatus.CLOSED})


class TriageStatus(StrEnum):
    PENDING = "PENDING"
    DONE = "DONE"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class Category(StrEnum):
    ACCESS = "ACCESS"
    BILLING = "BILLING"
    BUG = "BUG"
    DATABASE = "DATABASE"
    FEATURE_REQUEST = "FEATURE_REQUEST"
    HARDWARE = "HARDWARE"
    HR_POLICY = "HR_POLICY"
    INFRASTRUCTURE = "INFRASTRUCTURE"
    PAYROLL = "PAYROLL"
    OTHER = "OTHER"


class Severity(StrEnum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


SEVERITY_RANK = {Severity.CRITICAL: 0, Severity.HIGH: 1, Severity.MEDIUM: 2, Severity.LOW: 3}


class Sentiment(StrEnum):
    FRUSTRATED = "FRUSTRATED"
    NEUTRAL = "NEUTRAL"
    POSITIVE = "POSITIVE"


class EventType(StrEnum):
    CREATED = "CREATED"
    TRIAGED = "TRIAGED"
    STATUS_CHANGED = "STATUS_CHANGED"
    ASSIGNED = "ASSIGNED"
    NOTE = "NOTE"
    REPLY = "REPLY"
    REOPENED = "REOPENED"
    FEEDBACK = "FEEDBACK"
