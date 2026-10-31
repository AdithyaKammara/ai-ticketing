"""Pure domain rules: no database, no network."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from app.core.clock import utcnow, uuid7
from app.core.errors import AppError
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.db.enums import Availability, Role, Severity, TicketStatus
from app.services import routing, sla, workflow
from app.services.pagination import decode_cursor, encode_cursor
from app.services.routing import Candidate, pick_assignee
from app.services.skills import normalize_skills, slugify_skill

S = TicketStatus
SECRET = "unit-test-secret-that-is-long-enough"


def candidate(
    name: str,
    skills: set[str] | None = None,
    load: int = 0,
    availability: Availability = Availability.AVAILABLE,
) -> Candidate:
    return Candidate(uuid4(), name, frozenset(skills or set()), load, availability)


# ------------------------------------------------------------------ workflow (FR-3)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (S.NEW, S.IN_PROGRESS),
        (S.IN_PROGRESS, S.WAITING_ON_REQUESTER),
        (S.WAITING_ON_REQUESTER, S.IN_PROGRESS),
        (S.IN_PROGRESS, S.RESOLVED),
        (S.RESOLVED, S.CLOSED),
        (S.AUTO_RESOLVED, S.CLOSED),
    ],
)
def test_allowed_manual_transitions(current: TicketStatus, target: TicketStatus) -> None:
    assert workflow.can_transition(current, target)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (S.CLOSED, S.IN_PROGRESS),
        (S.TRIAGING, S.IN_PROGRESS),
        (S.NEW, S.AUTO_RESOLVED),
        (S.IN_PROGRESS, S.NEW),
        (S.RESOLVED, S.NEW),
        (S.IN_PROGRESS, S.TRIAGING),
    ],
)
def test_forbidden_manual_transitions(current: TicketStatus, target: TicketStatus) -> None:
    assert not workflow.can_transition(current, target)


def test_only_the_system_can_auto_resolve_or_reopen() -> None:
    assert workflow.can_transition(S.TRIAGING, S.AUTO_RESOLVED, system=True)
    assert workflow.can_transition(S.RESOLVED, S.NEW, system=True)
    assert not workflow.can_transition(S.CLOSED, S.NEW, system=True)


def test_invalid_transition_error_names_both_states() -> None:
    with pytest.raises(AppError) as exc_info:
        workflow.ensure_transition(S.CLOSED, S.IN_PROGRESS)

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "INVALID_TRANSITION"
    assert exc_info.value.message == "Cannot move CLOSED to IN_PROGRESS"


def test_every_status_has_a_transition_entry() -> None:
    assert set(workflow.MANUAL_TRANSITIONS) == set(TicketStatus)


# ------------------------------------------------------------------ routing (FR-4)


def test_skill_match_uses_tags_not_substrings() -> None:
    # v1 matched "sql" inside "mysql"; tags must match exactly after normalization.
    sql_fan = candidate("A", {"sql"})
    mysql_expert = candidate("B", {"mysql"})

    assert routing.score(sql_fan, {"mysql"}) == 0
    assert routing.score(mysql_expert, {"mysql"}) == 3
    assert pick_assignee([sql_fan, mysql_expert], {"mysql"}) == mysql_expert


def test_skill_names_normalize_to_tags() -> None:
    assert slugify_skill("  Active Directory ") == "active-directory"
    assert slugify_skill("CI/CD") == "ci-cd"
    assert normalize_skills(["PostgreSQL", "postgresql", " ", "AWS"]) == {"postgresql", "aws"}


def test_score_combines_skills_load_and_busy_penalty() -> None:
    busy = candidate("A", {"vpn", "sso"}, load=1, availability=Availability.BUSY)

    assert routing.score(busy, {"vpn", "sso"}) == 3 * 2 - 1 - 2


def test_agent_on_leave_never_assigned() -> None:
    on_leave = candidate("Expert", {"vpn", "sso"}, availability=Availability.ON_LEAVE)
    novice = candidate("Novice", set(), load=5)

    assert pick_assignee([on_leave, novice], {"vpn", "sso"}) == novice
    assert pick_assignee([on_leave], {"vpn"}) is None


def test_empty_department_has_no_assignee() -> None:
    assert pick_assignee([], {"vpn"}) is None


def test_skill_tie_goes_to_lighter_load() -> None:
    heavy = candidate("A", {"vpn"}, load=2)
    light = candidate("B", {"vpn"}, load=1)

    assert pick_assignee([heavy, light], {"vpn"}) == light


def test_load_tie_goes_to_better_skill_match() -> None:
    one_skill = candidate("A", {"vpn"}, load=1)
    two_skills = candidate("B", {"vpn", "sso"}, load=1)

    assert pick_assignee([one_skill, two_skills], {"vpn", "sso"}) == two_skills


def test_full_tie_is_broken_by_name_deterministically() -> None:
    zed = candidate("Zed", {"vpn"})
    amy = candidate("Amy", {"vpn"})

    assert pick_assignee([zed, amy], {"vpn"}) == amy
    assert pick_assignee([amy, zed], {"vpn"}) == amy


def test_busy_agent_loses_to_equal_available_agent() -> None:
    busy = candidate("A", {"vpn"}, availability=Availability.BUSY)
    free = candidate("B", {"vpn"}, load=1)

    assert pick_assignee([busy, free], {"vpn"}) == free


# ------------------------------------------------------------------ SLA (FR-7)


@pytest.mark.parametrize(
    ("severity", "first", "resolve"),
    [
        (Severity.CRITICAL, timedelta(minutes=30), timedelta(hours=4)),
        (Severity.HIGH, timedelta(hours=2), timedelta(days=1)),
        (Severity.MEDIUM, timedelta(hours=8), timedelta(days=3)),
        (Severity.LOW, timedelta(days=1), timedelta(days=5)),
    ],
)
def test_sla_due_times(severity: Severity, first: timedelta, resolve: timedelta) -> None:
    start = datetime(2026, 10, 30, 9, 0, tzinfo=UTC)

    assert sla.due_times(severity, start) == (start + first, start + resolve)


def test_sla_rejects_naive_start_time() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        sla.due_times(Severity.LOW, datetime(2026, 10, 30, 9, 0))


# ------------------------------------------------------------------ security and ids


def test_password_hash_round_trip() -> None:
    hashed = hash_password("a-long-password")

    assert hashed.startswith("$argon2")
    assert verify_password("a-long-password", hashed)
    assert not verify_password("wrong-password", hashed)
    assert not verify_password("anything", None)


def test_access_token_round_trip() -> None:
    user_id = uuid4()
    token = create_access_token(user_id, Role.AGENT, SECRET, ttl_minutes=15)

    assert decode_access_token(token, SECRET) == user_id
    assert decode_access_token(token, "another-secret-of-sufficient-length!") is None
    assert decode_access_token("not-a-jwt", SECRET) is None


def test_expired_access_token_is_rejected() -> None:
    token = create_access_token(uuid4(), Role.AGENT, SECRET, ttl_minutes=-1)

    assert decode_access_token(token, SECRET) is None


def test_refresh_tokens_are_stored_as_hashes() -> None:
    digest = hash_refresh_token("raw-token")

    assert len(digest) == 64
    assert "raw-token" not in digest


def test_timestamps_are_timezone_aware() -> None:
    assert utcnow().tzinfo is not None


def test_uuid7_is_version_7_and_time_ordered() -> None:
    first, second = uuid7(), uuid7()

    assert first.version == 7
    assert first.variant == "specified in RFC 4122"
    assert first.int >> 80 <= second.int >> 80


# ------------------------------------------------------------------ cursors


def test_cursor_round_trip() -> None:
    values: list[datetime | int | UUID] = [1, datetime(2026, 10, 30, tzinfo=UTC), uuid4()]

    assert decode_cursor(encode_cursor(values), 3) == values


@pytest.mark.parametrize("bad", ["not-base64!", "eyJ4IjoxfQ", encode_cursor([1])])
def test_invalid_cursor_is_rejected(bad: str) -> None:
    with pytest.raises(AppError) as exc_info:
        decode_cursor(bad, 3)

    assert exc_info.value.code == "INVALID_CURSOR"


# ------------------------------------------------------------------ database URLs


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        ("postgresql://u:p@localhost:5432/db", "postgresql+asyncpg://u:p@localhost:5432/db"),
        ("postgres://u:p@h/db", "postgresql+asyncpg://u:p@h/db"),
        (
            "postgresql://u:p@ep-x.aws.neon.tech/neondb?sslmode=require&channel_binding=require",
            "postgresql+asyncpg://u:p@ep-x.aws.neon.tech/neondb?ssl=require",
        ),
    ],
)
def test_database_url_is_translated_for_asyncpg(given: str, expected: str) -> None:
    from app.db.session import async_database_url

    assert async_database_url(given) == expected
