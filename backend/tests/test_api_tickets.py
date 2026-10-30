from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utcnow
from app.db.enums import Availability, Category, EventType, Role, Severity, TicketStatus
from app.db.models import Department, Ticket, TicketEvent, User
from tests.conftest import Factory, FakeQueue, auth

NEW_TICKET = {
    "title": "Can't log in to VPN",
    "description": "Since this morning the VPN client says my credentials are invalid.",
}


@pytest.fixture
async def eng(make: Factory) -> Department:
    return await make.department("engineering")


@pytest.fixture
async def requester(make: Factory) -> User:
    return await make.user(Role.REQUESTER, name="Priya")


@pytest.fixture
async def agent(make: Factory, eng: Department) -> User:
    return await make.user(Role.AGENT, eng, name="Ravi")


@pytest.fixture
async def admin(make: Factory) -> User:
    return await make.user(Role.ADMIN, name="Meena")


# ------------------------------------------------------------------ create (FR-2)


async def test_fr2_create_returns_201_as_triaging_and_enqueues_triage(
    client: AsyncClient, requester: User, queue: FakeQueue
) -> None:
    response = await client.post("/api/v1/tickets", json=NEW_TICKET, headers=auth(requester))

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "TRIAGING"
    assert body["triage_status"] == "PENDING"
    assert body["number"].startswith("TKT-")
    assert body["created_at"].endswith("Z")
    assert [str(i) for i in queue.enqueued] == [body["id"]]


async def test_fr2_ticket_saved_when_triage_cannot_be_queued(
    client: AsyncClient, requester: User, admin: User, queue: FakeQueue
) -> None:
    queue.fail = True

    response = await client.post("/api/v1/tickets", json=NEW_TICKET, headers=auth(requester))

    assert response.status_code == 201
    assert response.json()["status"] == "NEW"
    assert response.json()["triage_status"] == "FAILED"
    unassigned = await client.get(
        "/api/v1/tickets", params={"unassigned": True}, headers=auth(admin)
    )
    assert [t["id"] for t in unassigned.json()["items"]] == [response.json()["id"]]


async def test_fr2_ticket_numbers_increase(client: AsyncClient, requester: User) -> None:
    first = await client.post("/api/v1/tickets", json=NEW_TICKET, headers=auth(requester))
    second = await client.post("/api/v1/tickets", json=NEW_TICKET, headers=auth(requester))

    def number(r: object) -> int:
        return int(r.json()["number"].removeprefix("TKT-"))  # type: ignore[attr-defined]

    assert number(second) == number(first) + 1


@pytest.mark.parametrize(
    "payload",
    [
        {"title": "Hi", "description": NEW_TICKET["description"]},
        {"title": NEW_TICKET["title"], "description": "too short"},
        {"title": NEW_TICKET["title"], "description": "x" * 5001},
    ],
)
async def test_fr2_create_validates_lengths(
    client: AsyncClient, requester: User, payload: dict[str, str]
) -> None:
    response = await client.post("/api/v1/tickets", json=payload, headers=auth(requester))

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_fr2_eleventh_ticket_in_an_hour_is_rate_limited(
    client: AsyncClient, requester: User
) -> None:
    for _ in range(10):
        ok = await client.post("/api/v1/tickets", json=NEW_TICKET, headers=auth(requester))
        assert ok.status_code == 201

    response = await client.post("/api/v1/tickets", json=NEW_TICKET, headers=auth(requester))

    assert response.status_code == 429
    assert "10 tickets an hour" in response.json()["error"]["message"]


async def test_create_requires_authentication(client: AsyncClient) -> None:
    assert (await client.post("/api/v1/tickets", json=NEW_TICKET)).status_code == 401


# ------------------------------------------------------------------ visibility


async def test_requester_cannot_read_others_tickets(
    client: AsyncClient, make: Factory, requester: User
) -> None:
    other = await make.user(Role.REQUESTER)
    mine = await make.ticket(requester)
    theirs = await make.ticket(other)

    listed = await client.get("/api/v1/tickets", headers=auth(requester))
    direct = await client.get(f"/api/v1/tickets/{theirs.id}", headers=auth(requester))

    assert [t["id"] for t in listed.json()["items"]] == [str(mine.id)]
    assert direct.status_code == 404


async def test_agent_sees_own_department_and_assigned_tickets_only(
    client: AsyncClient, make: Factory, requester: User, agent: User, eng: Department
) -> None:
    it = await make.department("it")
    in_dept = await make.ticket(requester, department=eng)
    assigned_elsewhere = await make.ticket(requester, department=it, assignee=agent)
    hidden = await make.ticket(requester, department=it)

    listed = await client.get("/api/v1/tickets", headers=auth(agent))
    ids = {t["id"] for t in listed.json()["items"]}

    assert ids == {str(in_dept.id), str(assigned_elsewhere.id)}
    assert (
        await client.get(f"/api/v1/tickets/{hidden.id}", headers=auth(agent))
    ).status_code == 404


async def test_admin_sees_everything(
    client: AsyncClient, make: Factory, requester: User, admin: User
) -> None:
    await make.ticket(requester)
    await make.ticket(await make.user())

    listed = await client.get("/api/v1/tickets", headers=auth(admin))

    assert len(listed.json()["items"]) == 2


async def test_requester_does_not_see_ai_confidence(
    client: AsyncClient, make: Factory, requester: User, admin: User
) -> None:
    ticket = await make.ticket(requester, ai_confidence=91, ai_summary="VPN issue")

    as_requester = await client.get(f"/api/v1/tickets/{ticket.id}", headers=auth(requester))
    as_admin = await client.get(f"/api/v1/tickets/{ticket.id}", headers=auth(admin))

    assert as_requester.json()["ai_confidence"] is None
    assert as_admin.json()["ai_confidence"] == 91


# ------------------------------------------------------------------ listing (FR-5)


async def test_list_paginates_with_cursor_without_duplicates(
    client: AsyncClient, make: Factory, requester: User
) -> None:
    created = {str((await make.ticket(requester)).id) for _ in range(7)}

    seen: list[str] = []
    cursor = None
    for _ in range(4):
        params: dict[str, str | int] = {"limit": 3}
        if cursor:
            params["cursor"] = cursor
        page = (await client.get("/api/v1/tickets", params=params, headers=auth(requester))).json()
        seen += [t["id"] for t in page["items"]]
        cursor = page["next_cursor"]
        if cursor is None:
            break

    assert len(seen) == 7
    assert set(seen) == created


@pytest.mark.parametrize("sort", ["-created_at", "created_at", "due", "severity"])
async def test_every_sort_pages_through_all_tickets(
    client: AsyncClient, make: Factory, requester: User, sort: str
) -> None:
    for severity in (Severity.LOW, Severity.CRITICAL, None, Severity.HIGH, Severity.MEDIUM):
        await make.ticket(
            requester,
            severity=severity,
            resolve_due_at=utcnow() + timedelta(hours=1) if severity else None,
        )

    ids: list[str] = []
    cursor = None
    while True:
        params: dict[str, str | int] = {"limit": 2, "sort": sort}
        if cursor:
            params["cursor"] = cursor
        page = (await client.get("/api/v1/tickets", params=params, headers=auth(requester))).json()
        ids += [t["id"] for t in page["items"]]
        cursor = page["next_cursor"]
        if cursor is None:
            break

    assert len(ids) == len(set(ids)) == 5


async def test_severity_sort_puts_critical_first(
    client: AsyncClient, make: Factory, requester: User
) -> None:
    for severity in (Severity.LOW, Severity.CRITICAL, Severity.MEDIUM):
        await make.ticket(requester, severity=severity)

    page = await client.get("/api/v1/tickets", params={"sort": "severity"}, headers=auth(requester))

    assert [t["severity"] for t in page.json()["items"]] == ["CRITICAL", "MEDIUM", "LOW"]


async def test_fr7_overdue_tickets_sort_first_and_are_flagged(
    client: AsyncClient, make: Factory, requester: User
) -> None:
    on_time = await make.ticket(requester, resolve_due_at=utcnow() + timedelta(days=1))
    overdue = await make.ticket(requester, resolve_due_at=utcnow() - timedelta(hours=1))
    await make.ticket(
        requester, status=TicketStatus.RESOLVED, resolve_due_at=utcnow() - timedelta(hours=1)
    )

    page = (await client.get("/api/v1/tickets", headers=auth(requester))).json()["items"]
    only_overdue = await client.get(
        "/api/v1/tickets", params={"overdue": True}, headers=auth(requester)
    )
    not_overdue = await client.get(
        "/api/v1/tickets", params={"overdue": False}, headers=auth(requester)
    )

    assert page[0]["id"] == str(overdue.id)
    assert page[0]["is_overdue"] is True
    assert [t["id"] for t in only_overdue.json()["items"]] == [str(overdue.id)]
    assert str(on_time.id) in {t["id"] for t in not_overdue.json()["items"]}


async def test_list_filters(
    client: AsyncClient, make: Factory, requester: User, agent: User, admin: User, eng: Department
) -> None:
    vpn = await make.ticket(
        requester,
        title="VPN 50% down",
        category=Category.ACCESS,
        severity=Severity.HIGH,
        department=eng,
        assignee=agent,
        status=TicketStatus.IN_PROGRESS,
    )
    await make.ticket(requester, title="Laptop broken", category=Category.HARDWARE)

    async def ids(**params: str | bool) -> list[str]:
        response = await client.get("/api/v1/tickets", params=params, headers=auth(admin))
        assert response.status_code == 200, response.text
        return [t["id"] for t in response.json()["items"]]

    expected = [str(vpn.id)]
    assert await ids(q="vpn") == expected
    assert await ids(q="50%") == expected
    assert await ids(status="IN_PROGRESS") == expected
    assert await ids(severity="HIGH") == expected
    assert await ids(category="ACCESS") == expected
    assert await ids(department_id=str(eng.id)) == expected
    assert await ids(assignee_id=str(agent.id)) == expected
    assert await ids(unassigned=False) == expected
    assert await ids(requester_id=str(requester.id), category="HARDWARE") != expected


async def test_invalid_cursor_returns_400(client: AsyncClient, requester: User) -> None:
    response = await client.get(
        "/api/v1/tickets", params={"cursor": "garbage"}, headers=auth(requester)
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_CURSOR"


# ------------------------------------------------------------------ status workflow (FR-3)


async def test_agent_moves_ticket_through_the_workflow(
    client: AsyncClient, make: Factory, requester: User, agent: User, eng: Department
) -> None:
    ticket = await make.ticket(requester, department=eng, assignee=agent)

    for status in ("IN_PROGRESS", "WAITING_ON_REQUESTER", "IN_PROGRESS", "RESOLVED", "CLOSED"):
        response = await client.patch(
            f"/api/v1/tickets/{ticket.id}/status", json={"status": status}, headers=auth(agent)
        )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == status

    body = response.json()
    assert body["resolved_at"].endswith("Z")
    assert body["closed_at"].endswith("Z")
    events = await client.get(f"/api/v1/tickets/{ticket.id}/events", headers=auth(agent))
    changes = [e for e in events.json() if e["type"] == "STATUS_CHANGED"]
    assert [(e["from_value"], e["to_value"]) for e in changes][-1] == ("RESOLVED", "CLOSED")
    assert changes[0]["actor"]["id"] == str(agent.id)


async def test_invalid_status_transition_returns_409(
    client: AsyncClient, make: Factory, requester: User, admin: User
) -> None:
    ticket = await make.ticket(requester, status=TicketStatus.CLOSED)

    response = await client.patch(
        f"/api/v1/tickets/{ticket.id}/status", json={"status": "IN_PROGRESS"}, headers=auth(admin)
    )

    assert response.status_code == 409
    assert response.json()["error"] == {
        "code": "INVALID_TRANSITION",
        "message": "Cannot move CLOSED to IN_PROGRESS",
        "details": {"from": "CLOSED", "to": "IN_PROGRESS"},
    }


async def test_requester_cannot_change_status(
    client: AsyncClient, make: Factory, requester: User
) -> None:
    ticket = await make.ticket(requester)

    response = await client.patch(
        f"/api/v1/tickets/{ticket.id}/status", json={"status": "RESOLVED"}, headers=auth(requester)
    )

    assert response.status_code == 403


async def test_agent_cannot_work_a_ticket_they_only_requested(
    client: AsyncClient, make: Factory, agent: User
) -> None:
    ticket = await make.ticket(agent, department=await make.department("it"))

    response = await client.patch(
        f"/api/v1/tickets/{ticket.id}/status", json={"status": "IN_PROGRESS"}, headers=auth(agent)
    )

    assert response.status_code == 403


# ------------------------------------------------------------------ reassign (FR-4)


async def test_reassign_logs_the_reason(
    client: AsyncClient, make: Factory, requester: User, agent: User, eng: Department
) -> None:
    colleague = await make.user(Role.AGENT, eng, name="Lena")
    ticket = await make.ticket(requester, department=eng, assignee=agent)

    response = await client.patch(
        f"/api/v1/tickets/{ticket.id}/assignee",
        json={"assignee_id": str(colleague.id), "reason": "Lena owns checkout"},
        headers=auth(agent),
    )

    assert response.status_code == 200
    assert response.json()["assignee"]["id"] == str(colleague.id)
    events = (await client.get(f"/api/v1/tickets/{ticket.id}/events", headers=auth(agent))).json()
    assigned = [e for e in events if e["type"] == "ASSIGNED"][-1]
    assert (assigned["from_value"], assigned["to_value"]) == ("Ravi", "Lena")
    assert assigned["body"] == "Lena owns checkout"


async def test_reassign_to_nobody_returns_ticket_to_unassigned(
    client: AsyncClient, make: Factory, requester: User, agent: User, eng: Department
) -> None:
    ticket = await make.ticket(requester, department=eng, assignee=agent)

    response = await client.patch(
        f"/api/v1/tickets/{ticket.id}/assignee",
        json={"assignee_id": None, "reason": "Needs a specialist"},
        headers=auth(agent),
    )

    assert response.json()["assignee"] is None


async def test_reassign_rejects_agents_on_leave_and_non_agents(
    client: AsyncClient,
    make: Factory,
    requester: User,
    admin: User,
    eng: Department,
) -> None:
    on_leave = await make.user(Role.AGENT, eng, availability=Availability.ON_LEAVE)
    ticket = await make.ticket(requester, department=eng)

    for target in (on_leave, requester):
        response = await client.patch(
            f"/api/v1/tickets/{ticket.id}/assignee",
            json={"assignee_id": str(target.id), "reason": "try it"},
            headers=auth(admin),
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "INVALID_ASSIGNEE"


async def test_agent_cannot_reassign_into_another_department(
    client: AsyncClient, make: Factory, requester: User, agent: User, eng: Department
) -> None:
    outsider = await make.user(Role.AGENT, await make.department("it"))
    ticket = await make.ticket(requester, department=eng, assignee=agent)

    response = await client.patch(
        f"/api/v1/tickets/{ticket.id}/assignee",
        json={"assignee_id": str(outsider.id), "reason": "wrong team"},
        headers=auth(agent),
    )

    assert response.status_code == 403


async def test_admin_reassign_moves_ticket_to_the_new_department(
    client: AsyncClient, make: Factory, requester: User, admin: User, eng: Department
) -> None:
    it = await make.department("it")
    it_agent = await make.user(Role.AGENT, it)
    ticket = await make.ticket(requester, department=eng)

    response = await client.patch(
        f"/api/v1/tickets/{ticket.id}/assignee",
        json={"assignee_id": str(it_agent.id), "reason": "It is an access problem"},
        headers=auth(admin),
    )

    assert response.json()["department"]["id"] == str(it.id)


async def test_closed_tickets_cannot_be_reassigned(
    client: AsyncClient, make: Factory, requester: User, admin: User, agent: User
) -> None:
    ticket = await make.ticket(requester, status=TicketStatus.CLOSED)

    response = await client.patch(
        f"/api/v1/tickets/{ticket.id}/assignee",
        json={"assignee_id": str(agent.id), "reason": "late"},
        headers=auth(admin),
    )

    assert response.status_code == 409


# ------------------------------------------------------------- reopen and feedback (FR-3, FR-9)


async def test_requester_reopens_a_resolved_ticket_and_it_is_routed_again(
    client: AsyncClient, make: Factory, requester: User, agent: User, eng: Department
) -> None:
    await make.route(Category.BUG, eng, ["python"])
    ticket = await make.ticket(
        requester, status=TicketStatus.RESOLVED, department=eng, category=Category.BUG
    )

    response = await client.post(f"/api/v1/tickets/{ticket.id}/reopen", headers=auth(requester))

    assert response.status_code == 200
    assert response.json()["status"] == "NEW"
    assert response.json()["resolved_at"] is None
    assert response.json()["assignee"]["id"] == str(agent.id)


async def test_reopen_only_from_resolved_states(
    client: AsyncClient, make: Factory, requester: User
) -> None:
    ticket = await make.ticket(requester, status=TicketStatus.IN_PROGRESS)

    response = await client.post(f"/api/v1/tickets/{ticket.id}/reopen", headers=auth(requester))

    assert response.status_code == 409


async def test_only_the_requester_or_admin_can_reopen(
    client: AsyncClient, make: Factory, requester: User, agent: User, eng: Department
) -> None:
    ticket = await make.ticket(requester, status=TicketStatus.RESOLVED, department=eng)

    response = await client.post(f"/api/v1/tickets/{ticket.id}/reopen", headers=auth(agent))

    assert response.status_code == 403


async def test_fr9_helpful_feedback_is_recorded_once(
    client: AsyncClient, make: Factory, requester: User
) -> None:
    ticket = await make.ticket(requester, status=TicketStatus.AUTO_RESOLVED)

    first = await client.post(
        f"/api/v1/tickets/{ticket.id}/feedback", json={"helpful": True}, headers=auth(requester)
    )
    again = await client.post(
        f"/api/v1/tickets/{ticket.id}/feedback", json={"helpful": True}, headers=auth(requester)
    )

    assert first.json()["status"] == "AUTO_RESOLVED"
    assert first.json()["feedback_given"] is True
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "FEEDBACK_EXISTS"


async def test_fr9_not_helpful_reopens_the_ticket(
    client: AsyncClient, make: Factory, requester: User, db: AsyncSession
) -> None:
    ticket = await make.ticket(requester, status=TicketStatus.AUTO_RESOLVED)

    response = await client.post(
        f"/api/v1/tickets/{ticket.id}/feedback", json={"helpful": False}, headers=auth(requester)
    )

    assert response.json()["status"] == "NEW"
    types = list(
        await db.scalars(select(TicketEvent.type).where(TicketEvent.ticket_id == ticket.id))
    )
    assert EventType.FEEDBACK in types
    assert EventType.REOPENED in types


async def test_feedback_only_on_own_auto_resolved_tickets(
    client: AsyncClient, make: Factory, requester: User, admin: User
) -> None:
    resolved = await make.ticket(requester, status=TicketStatus.RESOLVED)
    auto = await make.ticket(requester, status=TicketStatus.AUTO_RESOLVED)

    not_auto = await client.post(
        f"/api/v1/tickets/{resolved.id}/feedback", json={"helpful": True}, headers=auth(requester)
    )
    not_mine = await client.post(
        f"/api/v1/tickets/{auto.id}/feedback", json={"helpful": True}, headers=auth(admin)
    )

    assert not_auto.status_code == 409
    assert not_mine.status_code == 403


# ------------------------------------------------------------------ comments and timeline


async def test_internal_notes_are_hidden_from_the_requester(
    client: AsyncClient, make: Factory, requester: User, agent: User, eng: Department
) -> None:
    ticket = await make.ticket(requester, department=eng, assignee=agent)
    await client.post(
        f"/api/v1/tickets/{ticket.id}/comments",
        json={"body": "Probably the cert rotation", "is_internal": True},
        headers=auth(agent),
    )
    await client.post(
        f"/api/v1/tickets/{ticket.id}/comments",
        json={"body": "Can you try again now?"},
        headers=auth(agent),
    )

    as_requester = await client.get(f"/api/v1/tickets/{ticket.id}/events", headers=auth(requester))
    as_agent = await client.get(f"/api/v1/tickets/{ticket.id}/events", headers=auth(agent))

    assert [e["body"] for e in as_requester.json()] == ["Can you try again now?"]
    assert len(as_agent.json()) == 2


async def test_first_public_reply_sets_first_responded_at(
    client: AsyncClient, make: Factory, requester: User, agent: User, eng: Department
) -> None:
    ticket = await make.ticket(requester, department=eng, assignee=agent)
    await client.post(
        f"/api/v1/tickets/{ticket.id}/comments",
        json={"body": "internal only", "is_internal": True},
        headers=auth(agent),
    )
    before = (await client.get(f"/api/v1/tickets/{ticket.id}", headers=auth(agent))).json()

    reply = await client.post(
        f"/api/v1/tickets/{ticket.id}/comments", json={"body": "On it"}, headers=auth(agent)
    )
    after = (await client.get(f"/api/v1/tickets/{ticket.id}", headers=auth(agent))).json()

    assert reply.status_code == 201
    assert reply.json()["type"] == "REPLY"
    assert before["first_responded_at"] is None
    assert after["first_responded_at"].endswith("Z")


async def test_requester_can_reply_publicly_but_not_internally(
    client: AsyncClient, make: Factory, requester: User
) -> None:
    ticket = await make.ticket(requester)

    public = await client.post(
        f"/api/v1/tickets/{ticket.id}/comments",
        json={"body": "Still broken"},
        headers=auth(requester),
    )
    internal = await client.post(
        f"/api/v1/tickets/{ticket.id}/comments",
        json={"body": "sneaky", "is_internal": True},
        headers=auth(requester),
    )

    assert public.status_code == 201
    assert internal.status_code == 403


async def test_no_comments_on_closed_tickets(
    client: AsyncClient, make: Factory, requester: User
) -> None:
    ticket = await make.ticket(requester, status=TicketStatus.CLOSED)

    response = await client.post(
        f"/api/v1/tickets/{ticket.id}/comments", json={"body": "hello?"}, headers=auth(requester)
    )

    assert response.status_code == 409


# ------------------------------------------------------------------ retriage


async def test_admin_can_retriage_a_new_ticket(
    client: AsyncClient, make: Factory, requester: User, admin: User, queue: FakeQueue
) -> None:
    ticket = await make.ticket(requester, status=TicketStatus.NEW)

    response = await client.post(f"/api/v1/tickets/{ticket.id}/retriage", headers=auth(admin))

    assert response.json()["status"] == "TRIAGING"
    assert response.json()["triage_status"] == "PENDING"
    assert queue.enqueued == [ticket.id]


async def test_retriage_falls_back_when_queue_is_down(
    client: AsyncClient, make: Factory, requester: User, admin: User, queue: FakeQueue
) -> None:
    ticket = await make.ticket(requester, status=TicketStatus.NEW)
    queue.fail = True

    response = await client.post(f"/api/v1/tickets/{ticket.id}/retriage", headers=auth(admin))

    assert response.json()["status"] == "NEW"
    assert response.json()["triage_status"] == "FAILED"


async def test_retriage_rules(
    client: AsyncClient, make: Factory, requester: User, admin: User, agent: User, eng: Department
) -> None:
    in_progress = await make.ticket(requester, status=TicketStatus.IN_PROGRESS)
    new = await make.ticket(requester, department=eng)

    wrong_state = await client.post(
        f"/api/v1/tickets/{in_progress.id}/retriage", headers=auth(admin)
    )
    not_admin = await client.post(f"/api/v1/tickets/{new.id}/retriage", headers=auth(agent))

    assert wrong_state.status_code == 409
    assert not_admin.status_code == 403


# ------------------------------------------------------------------ data integrity


async def test_timestamps_are_stored_timezone_aware(
    client: AsyncClient, requester: User, db: AsyncSession
) -> None:
    created = await client.post("/api/v1/tickets", json=NEW_TICKET, headers=auth(requester))

    ticket = await db.scalar(select(Ticket).where(Ticket.id == created.json()["id"]))

    assert ticket is not None
    assert ticket.created_at.tzinfo is not None
