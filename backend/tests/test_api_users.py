import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import Availability, Category, Role, TicketStatus
from app.db.models import Department, User
from app.services import routing
from tests.conftest import Factory, auth


@pytest.fixture
async def eng(make: Factory) -> Department:
    return await make.department("engineering")


@pytest.fixture
async def admin(make: Factory) -> User:
    return await make.user(Role.ADMIN, name="Meena")


@pytest.fixture
async def agent(make: Factory, eng: Department) -> User:
    return await make.user(Role.AGENT, eng, name="Ravi")


def new_agent(eng: Department, **overrides: object) -> dict[str, object]:
    return {
        "email": "lena@acme.example",
        "full_name": "Lena Fischer",
        "password": "a-long-password",
        "role": "AGENT",
        "department_id": str(eng.id),
        "skills": ["Python", "react"],
        **overrides,
    }


# ------------------------------------------------------------------ directory


async def test_agents_see_staff_but_not_requesters(
    client: AsyncClient, make: Factory, agent: User, admin: User
) -> None:
    await make.user(Role.REQUESTER)

    response = await client.get("/api/v1/users", headers=auth(agent))

    assert response.status_code == 200
    assert {u["role"] for u in response.json()} == {"AGENT", "ADMIN"}


async def test_requesters_cannot_list_users(client: AsyncClient, make: Factory) -> None:
    requester = await make.user()

    assert (await client.get("/api/v1/users", headers=auth(requester))).status_code == 403


async def test_directory_shows_live_open_load(
    client: AsyncClient, make: Factory, admin: User, agent: User, eng: Department
) -> None:
    requester = await make.user()
    await make.ticket(requester, department=eng, assignee=agent, status=TicketStatus.NEW)
    await make.ticket(requester, department=eng, assignee=agent, status=TicketStatus.RESOLVED)

    response = await client.get(
        "/api/v1/users", params={"role": "AGENT", "q": "rav"}, headers=auth(admin)
    )

    assert [(u["full_name"], u["open_tickets"]) for u in response.json()] == [("Ravi", 1)]


async def test_admin_can_include_inactive_users(
    client: AsyncClient, make: Factory, admin: User, eng: Department
) -> None:
    await make.user(Role.AGENT, eng, name="Gone", is_active=False)

    default = await client.get("/api/v1/users", headers=auth(admin))
    everyone = await client.get(
        "/api/v1/users",
        params={"include_inactive": True, "department_id": str(eng.id)},
        headers=auth(admin),
    )

    assert "Gone" not in {u["full_name"] for u in default.json()}
    assert "Gone" in {u["full_name"] for u in everyone.json()}


# ------------------------------------------------------------------ create and update (FR-6)


async def test_admin_creates_an_agent_with_normalized_skills(
    client: AsyncClient, make: Factory, admin: User, eng: Department
) -> None:
    await make.skill("python")
    await make.skill("react")

    response = await client.post("/api/v1/users", json=new_agent(eng), headers=auth(admin))

    assert response.status_code == 201
    assert [s["slug"] for s in response.json()["skills"]] == ["python", "react"]


async def test_duplicate_email_returns_409(
    client: AsyncClient, admin: User, eng: Department
) -> None:
    payload = new_agent(eng, skills=[])
    await client.post("/api/v1/users", json=payload, headers=auth(admin))

    response = await client.post(
        "/api/v1/users", json={**payload, "email": "LENA@acme.example"}, headers=auth(admin)
    )

    assert response.status_code == 409


async def test_unknown_skills_and_departments_are_rejected(
    client: AsyncClient, admin: User, eng: Department
) -> None:
    unknown_skill = await client.post(
        "/api/v1/users", json=new_agent(eng, skills=["cobol"]), headers=auth(admin)
    )
    no_department = await client.post(
        "/api/v1/users", json=new_agent(eng, skills=[], department_id=None), headers=auth(admin)
    )
    bad_department = await client.post(
        "/api/v1/users",
        json=new_agent(eng, skills=[], department_id="00000000-0000-7000-8000-000000000000"),
        headers=auth(admin),
    )

    assert unknown_skill.json()["error"]["details"] == {"skills": ["cobol"]}
    assert no_department.json()["error"]["code"] == "DEPARTMENT_REQUIRED"
    assert bad_department.json()["error"]["code"] == "UNKNOWN_DEPARTMENT"


async def test_agents_cannot_create_users(
    client: AsyncClient, agent: User, eng: Department
) -> None:
    response = await client.post("/api/v1/users", json=new_agent(eng), headers=auth(agent))

    assert response.status_code == 403


async def test_admin_updates_role_department_and_skills(
    client: AsyncClient, make: Factory, admin: User, agent: User
) -> None:
    it = await make.department("it")
    await make.skill("vpn")

    response = await client.patch(
        f"/api/v1/users/{agent.id}",
        json={"department_id": str(it.id), "skills": ["VPN"], "full_name": "Ravi K"},
        headers=auth(admin),
    )

    body = response.json()
    assert body["department"]["slug"] == "it"
    assert [s["slug"] for s in body["skills"]] == ["vpn"]
    assert body["full_name"] == "Ravi K"


async def test_agent_can_only_change_own_availability(
    client: AsyncClient, make: Factory, agent: User, eng: Department
) -> None:
    colleague = await make.user(Role.AGENT, eng)

    own = await client.patch(
        f"/api/v1/users/{agent.id}", json={"availability": "BUSY"}, headers=auth(agent)
    )
    own_role = await client.patch(
        f"/api/v1/users/{agent.id}", json={"role": "ADMIN"}, headers=auth(agent)
    )
    other = await client.patch(
        f"/api/v1/users/{colleague.id}", json={"availability": "ON_LEAVE"}, headers=auth(agent)
    )

    assert own.status_code == 200
    assert own.json()["availability"] == "BUSY"
    assert own_role.status_code == 403
    assert other.status_code == 403


async def test_agents_must_keep_a_department(client: AsyncClient, admin: User, agent: User) -> None:
    response = await client.patch(
        f"/api/v1/users/{agent.id}", json={"department_id": None}, headers=auth(admin)
    )

    assert response.json()["error"]["code"] == "DEPARTMENT_REQUIRED"


async def test_unknown_user_returns_404(client: AsyncClient, admin: User) -> None:
    response = await client.patch(
        "/api/v1/users/00000000-0000-7000-8000-000000000000",
        json={"availability": "BUSY"},
        headers=auth(admin),
    )

    assert response.status_code == 404


# ------------------------------------------------------------------ deactivate (FR-6)


async def test_deactivating_an_agent_returns_open_tickets_to_unassigned(
    client: AsyncClient, make: Factory, admin: User, agent: User, eng: Department
) -> None:
    requester = await make.user()
    open_ticket = await make.ticket(
        requester, department=eng, assignee=agent, status=TicketStatus.IN_PROGRESS
    )
    done_ticket = await make.ticket(
        requester, department=eng, assignee=agent, status=TicketStatus.RESOLVED
    )

    response = await client.delete(f"/api/v1/users/{agent.id}", headers=auth(admin))

    assert response.status_code == 204
    unassigned = await client.get(
        "/api/v1/tickets", params={"unassigned": True}, headers=auth(admin)
    )
    assert [t["id"] for t in unassigned.json()["items"]] == [str(open_ticket.id)]
    done = await client.get(f"/api/v1/tickets/{done_ticket.id}", headers=auth(admin))
    assert done.json()["assignee"]["id"] == str(agent.id)
    assert (await client.get("/api/v1/auth/me", headers=auth(agent))).status_code == 401
    again = await client.delete(f"/api/v1/users/{agent.id}", headers=auth(admin))
    assert again.status_code == 204


async def test_admin_cannot_deactivate_themselves(client: AsyncClient, admin: User) -> None:
    response = await client.delete(f"/api/v1/users/{admin.id}", headers=auth(admin))

    assert response.status_code == 409


# ------------------------------------------------------------------ routing against the database


async def test_open_load_counts_only_open_statuses(
    make: Factory, db: AsyncSession, agent: User, eng: Department
) -> None:
    requester = await make.user()
    for status in TicketStatus:
        await make.ticket(requester, department=eng, assignee=agent, status=status)

    assert await routing.open_load(db, agent.id) == 3  # NEW, IN_PROGRESS, WAITING_ON_REQUESTER


async def test_agent_on_leave_never_assigned_from_database(
    make: Factory, db: AsyncSession, eng: Department
) -> None:
    python = await make.skill("python")
    await make.user(
        Role.AGENT, eng, name="Expert", skills=[python], availability=Availability.ON_LEAVE
    )
    await make.user(Role.AGENT, eng, name="Gone", skills=[python], is_active=False)
    fallback = await make.user(Role.AGENT, eng, name="Fallback")

    assert await routing.choose_assignee(db, eng.id, {"python"}) == fallback.id


async def test_routing_prefers_skill_match_then_load(
    make: Factory, db: AsyncSession, eng: Department
) -> None:
    python = await make.skill("python")
    expert = await make.user(Role.AGENT, eng, name="Expert", skills=[python])
    other = await make.user(Role.AGENT, eng, name="Other")
    requester = await make.user()
    for _ in range(2):
        await make.ticket(requester, department=eng, assignee=expert)

    # 3 x 1 skill - 2 open = 1 beats 0 skills - 0 open = 0.
    assert await routing.choose_assignee(db, eng.id, {"python"}) == expert.id
    await make.ticket(requester, department=eng, assignee=expert)
    assert await routing.choose_assignee(db, eng.id, {"python"}) == other.id


# ------------------------------------------------------------------ reference data


async def test_reference_endpoints(client: AsyncClient, make: Factory, eng: Department) -> None:
    user = await make.user()
    await make.skill("python")
    await make.route(Category.BUG, eng, ["python"])

    departments = await client.get("/api/v1/departments", headers=auth(user))
    skills = await client.get("/api/v1/skills", headers=auth(user))
    categories = await client.get("/api/v1/categories", headers=auth(user))

    assert [d["slug"] for d in departments.json()] == ["engineering"]
    assert [s["slug"] for s in skills.json()] == ["python"]
    assert categories.json()[0]["category"] == "BUG"
    assert categories.json()[0]["department"]["slug"] == "engineering"
