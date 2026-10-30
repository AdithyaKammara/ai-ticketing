"""AI quality evaluation: `python -m app.evals.run [--limit N] [--write]`.

Runs the labeled dataset through the same prompt, parser, severity floors and guardrails
the worker uses, prints per-field accuracy, a category confusion matrix and any unsafe
auto-resolutions, and exits 1 when a section 1 target is missed. This is the only code
that calls the real model on purpose; tests use fakes.
"""

import argparse
import asyncio
import json
import statistics
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.db.enums import Category, Severity
from app.llm.base import LLMProvider
from app.llm.groq_provider import DEFAULT_MODEL, GroqProvider
from app.llm.prompts.triage_v3 import RouteInfo
from app.seed import DEPARTMENTS, ROUTES
from app.services import guardrails
from app.services.guardrails import Decision, GuardrailInput
from app.services.triage_model import PROMPT_VERSION, run_triage_model

BACKEND_DIR = Path(__file__).resolve().parents[2]
DATASET = BACKEND_DIR / "evals" / "dataset.jsonl"
REPORT = BACKEND_DIR.parent / "docs" / "eval-results.md"

TARGET_CATEGORY = 0.90
TARGET_DEPARTMENT = 0.90
TARGET_UNSAFE = 0
LATENCY_TARGET_MS = 10_000  # reported, not gated: free-tier rate limits distort it


class EvalSettings(BaseSettings):
    """Only what the eval needs, so it runs without a database or Redis."""

    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    groq_api_key: SecretStr | None = None
    llm_model: str = DEFAULT_MODEL
    auto_resolve_min_confidence: int = 85


@dataclass(frozen=True)
class Case:
    id: str
    title: str
    description: str
    category: str
    department: str
    severity: list[str]
    must_not_auto_resolve: bool
    tags: list[str]


@dataclass(frozen=True)
class Prediction:
    case: Case
    category: str | None
    department: str | None
    severity: str | None
    auto_resolved: bool
    confidence: int | None
    latency_ms: int
    error: str | None


@dataclass
class Report:
    predictions: list[Prediction]
    model: str
    started: datetime = field(default_factory=lambda: datetime.now(UTC))

    def _rate(self, hits: int) -> float:
        return hits / len(self.predictions) if self.predictions else 0.0

    @property
    def category_accuracy(self) -> float:
        return self._rate(sum(p.category == p.case.category for p in self.predictions))

    @property
    def department_accuracy(self) -> float:
        return self._rate(sum(p.department == p.case.department for p in self.predictions))

    @property
    def severity_accuracy(self) -> float:
        return self._rate(sum(p.severity in p.case.severity for p in self.predictions))

    @property
    def unsafe(self) -> list[Prediction]:
        return [p for p in self.predictions if p.auto_resolved and p.case.must_not_auto_resolve]

    @property
    def failures(self) -> list[Prediction]:
        return [p for p in self.predictions if p.error]

    @property
    def p95_latency_ms(self) -> int:
        latencies = sorted(p.latency_ms for p in self.predictions)
        if len(latencies) < 2:
            return latencies[0] if latencies else 0
        return round(statistics.quantiles(latencies, n=20)[-1])

    def tag_accuracy(self, tag: str) -> tuple[int, int]:
        tagged = [p for p in self.predictions if tag in p.case.tags]
        return sum(p.category == p.case.category for p in tagged), len(tagged)

    @property
    def passed(self) -> bool:
        return (
            self.category_accuracy >= TARGET_CATEGORY
            and self.department_accuracy >= TARGET_DEPARTMENT
            and len(self.unsafe) <= TARGET_UNSAFE
        )

    def confusion(self) -> dict[str, Counter[str]]:
        matrix: dict[str, Counter[str]] = {c.value: Counter() for c in Category}
        for p in self.predictions:
            matrix[p.case.category][p.category or "FAILED"] += 1
        return matrix

    def markdown(self) -> str:
        n = len(self.predictions)

        def mark(ok: bool) -> str:
            return "pass" if ok else "**FAIL**"

        injection_ok, injection_n = self.tag_accuracy("injection")
        vague_ok, vague_n = self.tag_accuracy("vague")
        auto = sum(p.auto_resolved for p in self.predictions)
        lines = [
            "# AI triage evaluation",
            "",
            f"Prompt `{PROMPT_VERSION}`, model `{self.model}`, {n} labeled tickets, "
            f"run {self.started:%Y-%m-%d %H:%M} UTC.",
            "",
            "| Metric | Result | Target | |",
            "| --- | --- | --- | --- |",
            f"| Category accuracy | {self.category_accuracy:.1%} | >= {TARGET_CATEGORY:.0%} | "
            f"{mark(self.category_accuracy >= TARGET_CATEGORY)} |",
            f"| Department routing accuracy | {self.department_accuracy:.1%} | "
            f">= {TARGET_DEPARTMENT:.0%} | {mark(self.department_accuracy >= TARGET_DEPARTMENT)} |",
            f"| Unsafe auto-resolutions | {len(self.unsafe)} | {TARGET_UNSAFE} | "
            f"{mark(len(self.unsafe) <= TARGET_UNSAFE)} |",
            f"| Severity within labeled band | {self.severity_accuracy:.1%} | report only | |",
            f"| Injection tickets classified correctly | {injection_ok}/{injection_n} | "
            "report only | |",
            f"| Vague tickets classified correctly | {vague_ok}/{vague_n} | report only | |",
            f"| Auto-resolved | {auto}/{n} | report only | |",
            f"| Model failures (after retries and repair) | {len(self.failures)} | report only | |",
            f"| Triage latency p95 | {self.p95_latency_ms / 1000:.1f} s | "
            f"<= {LATENCY_TARGET_MS // 1000} s | report only |",
            "",
            "## Category confusion matrix",
            "",
            "Rows are the labeled category, columns what the model chose.",
            "",
        ]
        matrix = self.confusion()
        columns = [c.value for c in Category] + (
            ["FAILED"] if any(m["FAILED"] for m in matrix.values()) else []
        )
        short = {c: c.replace("_", " ").title().replace(" ", "")[:8] for c in columns}
        lines.append("| | " + " | ".join(short[c] for c in columns) + " |")
        lines.append("| --- " * (len(columns) + 1) + "|")
        for label, row in matrix.items():
            if sum(row.values()):
                cells = [str(row[c]) if row[c] else "." for c in columns]
                lines.append(f"| {short[label]} | " + " | ".join(cells) + " |")

        wrong = [p for p in self.predictions if p.category != p.case.category]
        if wrong:
            lines += ["", "## Misclassified", ""]
            lines += [
                f"- `{p.case.id}` {p.case.title!r}: expected {p.case.category}, "
                f"got {p.category or 'nothing'}" + (f" ({p.error})" if p.error else "")
                for p in wrong
            ]
        if self.unsafe:
            lines += ["", "## Unsafe auto-resolutions", ""]
            lines += [f"- `{p.case.id}` {p.case.title!r}" for p in self.unsafe]
        return "\n".join(lines) + "\n"


def load_cases(path: Path = DATASET) -> list[Case]:
    with path.open(encoding="utf-8") as f:
        return [Case(**json.loads(line)) for line in f if line.strip()]


def production_routes() -> list[RouteInfo]:
    return [RouteInfo(c, DEPARTMENTS[r.department]) for c, r in ROUTES.items()]


async def predict(provider: LLMProvider, case: Case, min_confidence: int) -> Prediction:
    outcome = await run_triage_model(provider, case.title, case.description, production_routes())
    result = outcome.result
    if result is None:
        return Prediction(case, None, None, None, False, None, outcome.latency_ms, outcome.error)

    category = Category(result.category)
    route = ROUTES[category]
    severity = guardrails.apply_severity_floor(
        Severity(result.severity), route.severity_floor, case.title, case.description
    )
    verdict = guardrails.decide(
        GuardrailInput(
            category=category,
            severity=severity,
            can_self_serve=result.can_self_serve,
            draft_response=result.draft_response,
            confidence=result.confidence,
            category_allows_auto_resolve=route.auto_resolve_allowed,
            min_confidence=min_confidence,
            recently_reopened_auto_resolution=False,
        )
    )
    return Prediction(
        case=case,
        category=category.value,
        department=DEPARTMENTS[route.department],
        severity=severity.value,
        auto_resolved=verdict.decision is Decision.AUTO_RESOLVE,
        confidence=result.confidence,
        latency_ms=outcome.latency_ms,
        error=None,
    )


async def evaluate(
    provider: LLMProvider, cases: list[Case], min_confidence: int = 85, delay: float = 0.0
) -> Report:
    predictions = []
    for i, case in enumerate(cases, start=1):
        prediction = await predict(provider, case, min_confidence)
        predictions.append(prediction)
        status = "ok " if prediction.category == case.category else "MISS"
        print(f"[{i:3}/{len(cases)}] {status} {case.id} -> {prediction.category}", file=sys.stderr)
        if delay:
            await asyncio.sleep(delay)
    return Report(predictions, provider.model)


async def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate AI triage on the labeled dataset.")
    parser.add_argument("--limit", type=int, help="only the first N cases")
    parser.add_argument("--write", action="store_true", help=f"write {REPORT.name}")
    parser.add_argument("--delay", type=float, default=0.0, help="seconds between calls")
    args = parser.parse_args(argv)

    settings = EvalSettings()
    if settings.groq_api_key is None or not settings.groq_api_key.get_secret_value():
        print("GROQ_API_KEY is not set; the eval needs the real model.", file=sys.stderr)
        return 2
    provider = GroqProvider(settings.groq_api_key.get_secret_value(), settings.llm_model)
    cases = load_cases()[: args.limit]
    try:
        report = await evaluate(provider, cases, settings.auto_resolve_min_confidence, args.delay)
    finally:
        await provider.aclose()

    text = report.markdown()
    print(text)
    if args.write:
        REPORT.write_text(text, encoding="utf-8")
        print(f"Wrote {REPORT}", file=sys.stderr)
    return 0 if report.passed else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
