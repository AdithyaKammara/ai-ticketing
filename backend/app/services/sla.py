"""SLA due times by severity (FR-7)."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from app.db.enums import Severity


@dataclass(frozen=True)
class SlaTargets:
    first_response: timedelta
    resolution: timedelta


SLA_BY_SEVERITY: dict[Severity, SlaTargets] = {
    Severity.CRITICAL: SlaTargets(timedelta(minutes=30), timedelta(hours=4)),
    Severity.HIGH: SlaTargets(timedelta(hours=2), timedelta(days=1)),
    Severity.MEDIUM: SlaTargets(timedelta(hours=8), timedelta(days=3)),
    Severity.LOW: SlaTargets(timedelta(days=1), timedelta(days=5)),
}


def due_times(severity: Severity, start: datetime) -> tuple[datetime, datetime]:
    """Return (first_response_due_at, resolve_due_at) measured from `start`."""
    if start.tzinfo is None:
        raise ValueError("SLA start time must be timezone-aware")
    targets = SLA_BY_SEVERITY[severity]
    return start + targets.first_response, start + targets.resolution
