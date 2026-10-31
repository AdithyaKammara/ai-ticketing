"""Deterministic demo data: `python -m app.seed [--reset]`.

Creates 6 departments, the skill tags, the category map, 12 agents, the 3 demo logins and
40 sample tickets with pre-computed triage, so every dashboard has something to show.
The same input always produces the same people, tickets and assignments; only the
timestamps move, relative to when the seed runs.
"""

import argparse
import asyncio
import random
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utcnow
from app.core.config import get_settings
from app.core.security import hash_password
from app.db.base import Base
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
from app.db.models import (
    AiTriageLog,
    CategoryRoute,
    Department,
    Skill,
    Ticket,
    TicketEvent,
    User,
)
from app.db.session import create_engine, create_sessionmaker
from app.services import routing, sla

DEMO_PASSWORD = "ticketing-demo"  # noqa: S105  (public demo accounts, listed in the README)
DEMO_DOMAIN = "acme.example"
SEED = 42

DEPARTMENTS = {
    "engineering": "Engineering",
    "it": "IT",
    "finance": "Finance",
    "hr": "HR",
    "devops": "DevOps",
    "product": "Product",
}

SKILLS = {
    "active-directory": "Active Directory",
    "sso": "SSO",
    "vpn": "VPN",
    "laptops": "Laptops",
    "printers": "Printers",
    "networking": "Networking",
    "postgresql": "PostgreSQL",
    "mysql": "MySQL",
    "python": "Python",
    "react": "React",
    "kubernetes": "Kubernetes",
    "aws": "AWS",
    "terraform": "Terraform",
    "ci-cd": "CI/CD",
    "payroll": "Payroll",
    "invoicing": "Invoicing",
    "expenses": "Expenses",
    "benefits": "Benefits",
    "leave-policy": "Leave policy",
    "onboarding": "Onboarding",
    "roadmap": "Roadmap",
    "ux": "UX",
}


@dataclass(frozen=True)
class Route:
    department: str
    skills: tuple[str, ...]
    auto_resolve_allowed: bool
    severity_floor: Severity | None = None


ROUTES: dict[Category, Route] = {
    Category.ACCESS: Route("it", ("active-directory", "sso", "vpn"), True),
    Category.BILLING: Route("finance", ("invoicing",), False),
    Category.BUG: Route("engineering", ("python", "react"), False),
    Category.DATABASE: Route("engineering", ("postgresql", "mysql"), False, Severity.HIGH),
    Category.FEATURE_REQUEST: Route("product", ("roadmap", "ux"), False),
    Category.HARDWARE: Route("it", ("laptops", "printers"), True),
    Category.HR_POLICY: Route("hr", ("leave-policy", "benefits"), True),
    Category.INFRASTRUCTURE: Route(
        "devops", ("kubernetes", "aws", "terraform"), False, Severity.HIGH
    ),
    Category.PAYROLL: Route("finance", ("payroll",), True),
    Category.OTHER: Route("it", (), True),
}


@dataclass(frozen=True)
class Person:
    email: str
    name: str
    role: Role
    department: str | None = None
    skills: tuple[str, ...] = ()
    availability: Availability = Availability.AVAILABLE


DEMO_REQUESTER = Person(f"requester@{DEMO_DOMAIN}", "Priya Sharma", Role.REQUESTER)
DEMO_AGENT = Person(
    f"agent@{DEMO_DOMAIN}", "Ravi Kumar", Role.AGENT, "engineering", ("python", "postgresql")
)
DEMO_ADMIN = Person(f"admin@{DEMO_DOMAIN}", "Meena Iyer", Role.ADMIN)

AGENTS = [
    DEMO_AGENT,
    Person(
        f"lena.fischer@{DEMO_DOMAIN}",
        "Lena Fischer",
        Role.AGENT,
        "engineering",
        ("react", "python", "mysql"),
    ),
    Person(
        f"arjun.mehta@{DEMO_DOMAIN}",
        "Arjun Mehta",
        Role.AGENT,
        "it",
        ("active-directory", "sso", "vpn"),
    ),
    Person(
        f"sofia.rossi@{DEMO_DOMAIN}",
        "Sofia Rossi",
        Role.AGENT,
        "it",
        ("laptops", "printers", "networking"),
        Availability.BUSY,
    ),
    Person(
        f"daniel.okafor@{DEMO_DOMAIN}",
        "Daniel Okafor",
        Role.AGENT,
        "finance",
        ("payroll", "expenses"),
    ),
    Person(
        f"hannah.lee@{DEMO_DOMAIN}", "Hannah Lee", Role.AGENT, "finance", ("invoicing", "expenses")
    ),
    Person(
        f"fatima.khan@{DEMO_DOMAIN}", "Fatima Khan", Role.AGENT, "hr", ("leave-policy", "benefits")
    ),
    Person(
        f"tom.becker@{DEMO_DOMAIN}",
        "Tom Becker",
        Role.AGENT,
        "hr",
        ("onboarding", "benefits"),
        Availability.ON_LEAVE,
    ),
    Person(
        f"wei.zhang@{DEMO_DOMAIN}",
        "Wei Zhang",
        Role.AGENT,
        "devops",
        ("kubernetes", "aws", "ci-cd"),
    ),
    Person(
        f"maria.garcia@{DEMO_DOMAIN}", "Maria Garcia", Role.AGENT, "devops", ("terraform", "aws")
    ),
    Person(f"noah.wilson@{DEMO_DOMAIN}", "Noah Wilson", Role.AGENT, "product", ("roadmap", "ux")),
    Person(
        f"aisha.bello@{DEMO_DOMAIN}",
        "Aisha Bello",
        Role.AGENT,
        "product",
        ("ux",),
        Availability.BUSY,
    ),
]

REQUESTERS = [
    DEMO_REQUESTER,
    Person(f"james.clark@{DEMO_DOMAIN}", "James Clark", Role.REQUESTER),
    Person(f"ananya.rao@{DEMO_DOMAIN}", "Ananya Rao", Role.REQUESTER),
    Person(f"lucas.martin@{DEMO_DOMAIN}", "Lucas Martin", Role.REQUESTER),
]


@dataclass(frozen=True)
class Sample:
    title: str
    description: str
    category: Category
    severity: Severity
    sentiment: Sentiment
    summary: str
    confidence: int
    auto_response: str | None = None


SAMPLES = [
    Sample(
        "Password reset link expired",
        "I requested a password reset this morning but the link in the email says it has expired. I need to get into my account.",
        Category.ACCESS,
        Severity.LOW,
        Sentiment.NEUTRAL,
        "Expired self-service password reset link.",
        94,
        "Reset links last 30 minutes. Request a new one at the sign-in page and use it straight away; if it still fails, reply here and IT will reset it for you.",
    ),
    Sample(
        "VPN says my credentials are invalid",
        "Since this morning the VPN client rejects my credentials, although I can sign in to email with the same password.",
        Category.ACCESS,
        Severity.MEDIUM,
        Sentiment.FRUSTRATED,
        "VPN rejects valid domain credentials; email sign-in works.",
        81,
    ),
    Sample(
        "Need access to the finance shared drive",
        "I joined the finance team last week and need read access to the Finance shared drive for month-end reports.",
        Category.ACCESS,
        Severity.LOW,
        Sentiment.POSITIVE,
        "Access request for Finance shared drive (new team member).",
        88,
    ),
    Sample(
        "Laptop battery drains in an hour",
        "My work laptop battery goes from full to empty in about an hour, even with only the browser open.",
        Category.HARDWARE,
        Severity.LOW,
        Sentiment.NEUTRAL,
        "Laptop battery life severely degraded.",
        90,
        "Batteries under warranty are replaced free. Book a swap with the IT desk on the 2nd floor; bring the charger so they can test it too.",
    ),
    Sample(
        "Printer on floor 3 jams every page",
        "The printer next to the kitchen on floor 3 jams on every single page. Several of us have tried.",
        Category.HARDWARE,
        Severity.MEDIUM,
        Sentiment.FRUSTRATED,
        "Shared printer (floor 3) jams on every page.",
        86,
    ),
    Sample(
        "How many days of parental leave do I get?",
        "I am expecting a baby in March. How many weeks of parental leave am I entitled to, and how do I apply?",
        Category.HR_POLICY,
        Severity.LOW,
        Sentiment.POSITIVE,
        "Question about parental leave entitlement and process.",
        95,
        "Employees get 16 weeks of paid parental leave. Apply in the HR portal under Leave > Parental at least 8 weeks before your start date.",
    ),
    Sample(
        "Unclear policy on working from abroad",
        "Can I work from another country for three weeks next summer? The remote work policy does not mention this.",
        Category.HR_POLICY,
        Severity.LOW,
        Sentiment.NEUTRAL,
        "Question about working abroad temporarily; policy unclear.",
        72,
    ),
    Sample(
        "Payslip shows wrong overtime hours",
        "My October payslip shows 4 hours of overtime but I worked 12. My manager approved all of it in the system.",
        Category.PAYROLL,
        Severity.MEDIUM,
        Sentiment.FRUSTRATED,
        "Overtime under-paid on October payslip (4h vs 12h approved).",
        89,
    ),
    Sample(
        "When is the November pay date?",
        "When will November salaries be paid? I have heard it may move because of the holiday.",
        Category.PAYROLL,
        Severity.LOW,
        Sentiment.NEUTRAL,
        "Question about November pay date.",
        93,
        "November salaries are paid on the 27th, as usual; the holiday does not change it.",
    ),
    Sample(
        "Vendor invoice paid twice",
        "Invoice INV-2291 from our cloud vendor was paid twice this month. We need to recover the duplicate payment.",
        Category.BILLING,
        Severity.HIGH,
        Sentiment.NEUTRAL,
        "Duplicate payment of vendor invoice INV-2291.",
        91,
    ),
    Sample(
        "Expense report stuck in approval",
        "My expense report from the Berlin trip has been pending approval for three weeks; my manager says she approved it.",
        Category.BILLING,
        Severity.LOW,
        Sentiment.FRUSTRATED,
        "Expense report stuck in approval for 3 weeks.",
        84,
    ),
    Sample(
        "Checkout page throws a 500 error",
        "Customers report a 500 error when they click Pay on the checkout page. It started after yesterday's release.",
        Category.BUG,
        Severity.HIGH,
        Sentiment.FRUSTRATED,
        "Checkout page returns 500 on Pay since yesterday's release.",
        92,
    ),
    Sample(
        "Dashboard dates show the wrong timezone",
        "All dates on the internal sales dashboard are shown in UTC instead of local time, which confuses the team.",
        Category.BUG,
        Severity.MEDIUM,
        Sentiment.NEUTRAL,
        "Sales dashboard renders dates in UTC instead of local time.",
        87,
    ),
    Sample(
        "Reporting database queries time out",
        "Since this morning every query against the reporting database times out after 30 seconds. Reports are blocked.",
        Category.DATABASE,
        Severity.HIGH,
        Sentiment.FRUSTRATED,
        "Reporting DB queries timing out; reports blocked.",
        90,
    ),
    Sample(
        "Need a read replica for analytics",
        "The analytics team would like a read replica of the orders database so heavy queries stop slowing production.",
        Category.DATABASE,
        Severity.HIGH,
        Sentiment.NEUTRAL,
        "Request for an analytics read replica of the orders DB.",
        83,
    ),
    Sample(
        "Production down: API returns 503 for all users",
        "The public API has returned 503 for all users for the last ten minutes. Production down, customers affected.",
        Category.INFRASTRUCTURE,
        Severity.CRITICAL,
        Sentiment.FRUSTRATED,
        "Production API outage: 503 for all users.",
        97,
    ),
    Sample(
        "Staging cluster out of disk space",
        "Deploys to staging fail with 'no space left on device' on the build nodes.",
        Category.INFRASTRUCTURE,
        Severity.HIGH,
        Sentiment.NEUTRAL,
        "Staging build nodes out of disk; deploys failing.",
        89,
    ),
    Sample(
        "Add dark mode to the employee portal",
        "Could the employee portal get a dark mode? Many of us work late and the white background is harsh.",
        Category.FEATURE_REQUEST,
        Severity.LOW,
        Sentiment.POSITIVE,
        "Feature request: dark mode for the employee portal.",
        94,
    ),
    Sample(
        "Bulk export for the CRM contacts",
        "Sales would like to export all CRM contacts to CSV in one go instead of 100 at a time.",
        Category.FEATURE_REQUEST,
        Severity.LOW,
        Sentiment.NEUTRAL,
        "Feature request: bulk CSV export of CRM contacts.",
        90,
    ),
    Sample(
        "Office plants need watering",
        "The plants in the meeting rooms on floor 2 look like they have not been watered in weeks. Who looks after them?",
        Category.OTHER,
        Severity.LOW,
        Sentiment.NEUTRAL,
        "Question about who maintains office plants.",
        78,
    ),
]

# One status per ticket, cycling, so the demo always covers every queue and state.
STATUS_CYCLE = [
    TicketStatus.NEW,
    TicketStatus.IN_PROGRESS,
    TicketStatus.WAITING_ON_REQUESTER,
    TicketStatus.RESOLVED,
    TicketStatus.IN_PROGRESS,
    TicketStatus.CLOSED,
    TicketStatus.NEW,
    TicketStatus.RESOLVED,
]


async def reset(session: AsyncSession) -> None:
    tables = ", ".join(t.name for t in reversed(Base.metadata.sorted_tables))
    await session.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    await session.execute(text("ALTER SEQUENCE ticket_number_seq RESTART WITH 1001"))
    await session.commit()


async def seed(session: AsyncSession, now: datetime | None = None) -> bool:
    """Seed an empty database. Returns False (and changes nothing) if data already exists."""
    if await session.scalar(select(func.count()).select_from(Department)):
        return False
    now = now or utcnow()
    rng = random.Random(SEED)  # noqa: S311  (demo data, not security)
    password_hash = hash_password(DEMO_PASSWORD)

    departments = {slug: Department(slug=slug, name=name) for slug, name in DEPARTMENTS.items()}
    skills = {slug: Skill(slug=slug, name=name) for slug, name in SKILLS.items()}
    session.add_all([*departments.values(), *skills.values()])
    await session.flush()

    for category, route in ROUTES.items():
        session.add(
            CategoryRoute(
                category=category,
                department_id=departments[route.department].id,
                default_skills=list(route.skills),
                auto_resolve_allowed=route.auto_resolve_allowed,
                severity_floor=route.severity_floor,
            )
        )

    def make_user(person: Person) -> User:
        return User(
            email=person.email,
            full_name=person.name,
            password_hash=password_hash,
            role=person.role,
            department_id=departments[person.department].id if person.department else None,
            availability=person.availability,
            skills=[skills[s] for s in person.skills],
        )

    requesters = [make_user(p) for p in REQUESTERS]
    session.add_all([*requesters, make_user(DEMO_ADMIN), *(make_user(p) for p in AGENTS)])
    await session.flush()

    for i in range(40):
        sample = SAMPLES[i % len(SAMPLES)]
        requester = requesters[i % len(requesters)]
        created = now - timedelta(days=rng.uniform(0.2, 29), minutes=rng.randint(0, 59))
        await _seed_ticket(session, sample, requester, created, i, departments)

    await session.commit()
    return True


async def _seed_ticket(
    session: AsyncSession,
    sample: Sample,
    requester: User,
    created: datetime,
    index: int,
    departments: dict[str, Department],
) -> None:
    route = ROUTES[sample.category]
    auto = sample.auto_response is not None
    status = TicketStatus.AUTO_RESOLVED if auto else STATUS_CYCLE[index % len(STATUS_CYCLE)]
    first_due, resolve_due = sla.due_times(sample.severity, created)

    ticket = Ticket(
        title=sample.title,
        description=sample.description,
        requester_id=requester.id,
        department_id=departments[route.department].id,
        category=sample.category,
        severity=sample.severity,
        sentiment=sample.sentiment,
        status=status,
        triage_status=TriageStatus.DONE,
        ai_summary=sample.summary,
        ai_confidence=sample.confidence,
        auto_response=sample.auto_response,
        first_response_due_at=first_due,
        resolve_due_at=resolve_due,
        created_at=created,
        updated_at=created,
    )
    session.add(ticket)
    await session.flush()

    def event(event_type: EventType, at: datetime, **fields: object) -> None:
        session.add(
            TicketEvent(
                ticket_id=ticket.id, type=event_type, created_at=at, updated_at=at, **fields
            )
        )

    triaged_at = created + timedelta(seconds=4)
    event(EventType.CREATED, created, actor_id=requester.id)
    event(EventType.TRIAGED, triaged_at, to_value=sample.category.value)
    session.add(
        AiTriageLog(
            ticket_id=ticket.id,
            provider="seed",
            model="seed",
            prompt_version="seed",
            latency_ms=1800 + index * 37 % 900,
            parsed={
                "category": sample.category.value,
                "severity": sample.severity.value,
                "confidence": sample.confidence,
            },
            guardrail_decision="AUTO_RESOLVE" if auto else "ROUTE",
            created_at=triaged_at,
            updated_at=triaged_at,
        )
    )

    if auto:
        ticket.resolved_at = triaged_at
        event(EventType.STATUS_CHANGED, triaged_at, from_value="TRIAGING", to_value="AUTO_RESOLVED")
        return

    event(EventType.STATUS_CHANGED, triaged_at, from_value="TRIAGING", to_value="NEW")
    assignee_id = await routing.choose_assignee(
        session, departments[route.department].id, set(route.skills)
    )
    ticket.assignee_id = assignee_id
    if assignee_id is not None:
        assignee = await session.get(User, assignee_id)
        event(
            EventType.ASSIGNED,
            triaged_at,
            to_value=assignee.full_name if assignee else None,
            body="Routed automatically",
        )

    if status is TicketStatus.NEW:
        return
    worked_at = created + timedelta(minutes=20 + index % 7 * 10)
    ticket.first_responded_at = worked_at
    event(
        EventType.STATUS_CHANGED,
        worked_at,
        actor_id=assignee_id,
        from_value="NEW",
        to_value="IN_PROGRESS",
    )
    event(
        EventType.REPLY,
        worked_at,
        actor_id=assignee_id,
        body="Thanks for reporting this. I'm looking into it now.",
    )
    if status is TicketStatus.IN_PROGRESS:
        return
    if status is TicketStatus.WAITING_ON_REQUESTER:
        event(
            EventType.STATUS_CHANGED,
            worked_at + timedelta(hours=1),
            actor_id=assignee_id,
            from_value="IN_PROGRESS",
            to_value="WAITING_ON_REQUESTER",
        )
        return
    resolved_at = worked_at + timedelta(hours=3)
    ticket.resolved_at = resolved_at
    event(
        EventType.STATUS_CHANGED,
        resolved_at,
        actor_id=assignee_id,
        from_value="IN_PROGRESS",
        to_value="RESOLVED",
    )
    if status is TicketStatus.CLOSED:
        closed_at = resolved_at + timedelta(days=7)
        ticket.closed_at = closed_at
        event(EventType.STATUS_CHANGED, closed_at, from_value="RESOLVED", to_value="CLOSED")


async def main(reset_first: bool) -> None:
    settings = get_settings()
    engine = create_engine(str(settings.database_url))
    try:
        async with create_sessionmaker(engine)() as session:
            if reset_first:
                await reset(session)
            created = await seed(session)
    finally:
        await engine.dispose()
    if created:
        print(f"Seeded demo data. Sign in as requester/agent/admin@{DEMO_DOMAIN}.")
    else:
        print("Database already has data; nothing changed. Use --reset to start over.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--reset", action="store_true", help="delete all data first")
    asyncio.run(main(parser.parse_args().reset))
