"""The ticket status state machine (FR-3). Any move not listed here is rejected with 409."""

from app.core.errors import AppError
from app.db.enums import TicketStatus

S = TicketStatus

# Moves an agent or admin may make through PATCH /tickets/{id}/status.
MANUAL_TRANSITIONS: dict[TicketStatus, frozenset[TicketStatus]] = {
    S.TRIAGING: frozenset(),
    S.NEW: frozenset({S.IN_PROGRESS, S.WAITING_ON_REQUESTER, S.RESOLVED, S.CLOSED}),
    S.IN_PROGRESS: frozenset({S.WAITING_ON_REQUESTER, S.RESOLVED}),
    S.WAITING_ON_REQUESTER: frozenset({S.IN_PROGRESS, S.RESOLVED}),
    S.RESOLVED: frozenset({S.CLOSED}),
    S.AUTO_RESOLVED: frozenset({S.CLOSED}),
    S.CLOSED: frozenset(),
}

# Moves only the system makes: triage outcomes, admin re-triage, requester reopen, and the
# 7-day auto-close.
SYSTEM_TRANSITIONS: dict[TicketStatus, frozenset[TicketStatus]] = {
    S.TRIAGING: frozenset({S.NEW, S.AUTO_RESOLVED}),
    S.NEW: frozenset({S.TRIAGING}),
    S.RESOLVED: frozenset({S.NEW, S.CLOSED}),
    S.AUTO_RESOLVED: frozenset({S.NEW, S.CLOSED}),
}

REOPENABLE = frozenset({S.RESOLVED, S.AUTO_RESOLVED})


def can_transition(current: TicketStatus, target: TicketStatus, *, system: bool = False) -> bool:
    if target in MANUAL_TRANSITIONS[current]:
        return True
    return system and target in SYSTEM_TRANSITIONS.get(current, frozenset())


def ensure_transition(current: TicketStatus, target: TicketStatus, *, system: bool = False) -> None:
    if not can_transition(current, target, system=system):
        raise AppError(
            409,
            "INVALID_TRANSITION",
            f"Cannot move {current.value} to {target.value}",
            {"from": current.value, "to": target.value},
        )
