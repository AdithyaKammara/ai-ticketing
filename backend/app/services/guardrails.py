"""Deterministic guardrails (section 5). The model suggests; this code decides.

A ticket is auto-resolved only when every check passes. Anything else is routed to a
person, so a wrong or manipulated model answer can never close a serious ticket.
"""

import re
from dataclasses import dataclass, field
from enum import StrEnum

from app.db.enums import SEVERITY_RANK, Category, Severity

# Never auto-resolved, whatever the database or the model says.
NEVER_AUTO_RESOLVE = frozenset({Category.DATABASE, Category.INFRASTRUCTURE, Category.BUG})
AUTO_RESOLVE_SEVERITIES = frozenset({Severity.LOW, Severity.MEDIUM})

# Phrases that force CRITICAL regardless of the model's severity.
CRITICAL_PHRASES = re.compile(
    r"\b(production (is )?down|prod (is )?down|all users|every user|everyone is blocked|"
    r"data loss|lost (all )?(the )?data|security breach|ransomware)\b",
    re.IGNORECASE,
)


class Decision(StrEnum):
    AUTO_RESOLVE = "AUTO_RESOLVE"
    ROUTE = "ROUTE"


@dataclass(frozen=True)
class GuardrailInput:
    category: Category
    severity: Severity
    can_self_serve: bool
    draft_response: str | None
    confidence: int
    category_allows_auto_resolve: bool
    min_confidence: int
    recently_reopened_auto_resolution: bool


@dataclass(frozen=True)
class Verdict:
    decision: Decision
    reasons: list[str] = field(default_factory=list)


def max_severity(a: Severity, b: Severity) -> Severity:
    return a if SEVERITY_RANK[a] <= SEVERITY_RANK[b] else b


def apply_severity_floor(
    severity: Severity, category_floor: Severity | None, title: str, description: str
) -> Severity:
    """Raise (never lower) the model's severity using the category floor and keywords."""
    if category_floor is not None:
        severity = max_severity(severity, category_floor)
    if CRITICAL_PHRASES.search(f"{title}\n{description}"):
        severity = Severity.CRITICAL
    return severity


def decide(check: GuardrailInput) -> Verdict:
    reasons: list[str] = []
    if not check.can_self_serve:
        reasons.append("model did not mark it self-serve")
    if not (check.draft_response and check.draft_response.strip()):
        reasons.append("no draft response")
    if check.confidence < check.min_confidence:
        reasons.append(f"confidence {check.confidence} < {check.min_confidence}")
    if check.severity not in AUTO_RESOLVE_SEVERITIES:
        reasons.append(f"severity {check.severity.value}")
    if check.category in NEVER_AUTO_RESOLVE or not check.category_allows_auto_resolve:
        reasons.append(f"category {check.category.value} is not auto-resolvable")
    if check.recently_reopened_auto_resolution:
        reasons.append("requester reopened an automatic answer in the last 24 hours")
    return Verdict(Decision.ROUTE if reasons else Decision.AUTO_RESOLVE, reasons)
