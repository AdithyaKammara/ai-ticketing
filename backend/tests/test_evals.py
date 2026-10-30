"""The eval runner and dataset, exercised with a fake model (no network)."""

import json
from collections import Counter
from typing import Any

import pytest
from pydantic import SecretStr

from app.db.enums import Category
from app.evals import run
from app.evals.run import Case, EvalSettings, evaluate, load_cases
from app.llm.base import ChatMessage, LLMResponse
from app.seed import DEPARTMENTS, ROUTES


class LabelEcho:
    """Answers with the labeled category, except for ids listed in `wrong`."""

    name = "fake"
    model = "fake-model"

    def __init__(self, cases: list[Case], wrong: dict[str, str] | None = None) -> None:
        self.by_title = {c.title: c for c in cases}
        self.wrong = wrong or {}
        self.self_serve: set[str] = set()

    async def complete_json(self, messages: list[ChatMessage], max_tokens: int) -> LLMResponse:
        title = messages[-1].content.split("\n")[1]
        case = self.by_title[title]
        reply: dict[str, Any] = {
            "category": self.wrong.get(case.id, case.category),
            "severity": case.severity[0],
            "sentiment": "NEUTRAL",
            "summary": case.title,
            "suggested_skills": [],
            "can_self_serve": case.id in self.self_serve,
            "draft_response": "Steps." if case.id in self.self_serve else None,
            "confidence": 90,
            "reasoning": "fake",
        }
        return LLMResponse(json.dumps(reply), "fake", "fake-model")


def test_dataset_meets_the_prd_shape() -> None:
    cases = load_cases()
    tags = Counter(tag for c in cases for tag in c.tags)

    assert len(cases) >= 100
    assert len({c.id for c in cases}) == len(cases)
    assert tags["injection"] >= 10
    assert tags["vague"] >= 10
    assert {c.category for c in cases} == {category.value for category in ROUTES}
    for case in cases:
        assert case.department == DEPARTMENTS[ROUTES[Category(case.category)].department]
        assert case.severity
        assert set(case.severity) <= {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
        if "injection" in case.tags or "vague" in case.tags:
            assert case.must_not_auto_resolve


async def test_perfect_model_passes_every_target() -> None:
    cases = load_cases()

    report = await evaluate(LabelEcho(cases), cases)

    assert report.category_accuracy == 1.0
    assert report.department_accuracy == 1.0
    assert report.unsafe == []
    assert report.passed
    assert "| Category accuracy | 100.0% |" in report.markdown()


async def test_misclassifications_and_unsafe_answers_fail_the_run() -> None:
    cases = load_cases()[:20]
    model = LabelEcho(cases, wrong={cases[0].id: "OTHER", cases[1].id: "BILLING"})
    unsafe_case = next(c for c in cases if c.must_not_auto_resolve and c.category == "ACCESS")
    model.self_serve = {unsafe_case.id}

    report = await evaluate(model, cases)

    assert report.category_accuracy == 0.9
    assert [p.case.id for p in report.unsafe] == [unsafe_case.id]
    assert not report.passed
    text = report.markdown()
    assert "## Misclassified" in text
    assert "## Unsafe auto-resolutions" in text
    assert report.confusion()[cases[0].category]["OTHER"] == 1


async def test_model_failures_count_as_misses() -> None:
    cases = load_cases()[:3]

    class Broken:
        name = "fake"
        model = "fake-model"

        async def complete_json(self, messages: list[ChatMessage], max_tokens: int) -> LLMResponse:
            return LLMResponse("not json", "fake", "fake-model")

    report = await evaluate(Broken(), cases)

    assert len(report.failures) == 3
    assert report.category_accuracy == 0.0
    assert "Failed" in report.markdown()  # the FAILED column of the confusion matrix


async def test_main_refuses_to_run_without_a_key(monkeypatch: pytest.MonkeyPatch) -> None:
    no_key = EvalSettings.model_construct(groq_api_key=None)
    monkeypatch.setattr(run, "EvalSettings", lambda: no_key)

    assert await run.main([]) == 2


async def test_main_writes_the_report_and_sets_exit_code(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    cases = load_cases()[:5]
    report_path = tmp_path / "eval-results.md"
    monkeypatch.setattr(run, "REPORT", report_path)
    with_key = EvalSettings.model_construct(
        groq_api_key=SecretStr("gsk_test"), llm_model="m", auto_resolve_min_confidence=85
    )
    monkeypatch.setattr(run, "EvalSettings", lambda: with_key)

    class Provider(LabelEcho):
        def __init__(self, *_: object) -> None:
            super().__init__(cases)

        async def aclose(self) -> None:
            return None

    monkeypatch.setattr(run, "GroqProvider", Provider)

    assert await run.main(["--limit", "5", "--write"]) == 0
    assert report_path.read_text(encoding="utf-8").startswith("# AI triage evaluation")
