"""Calling the model for triage: validation, retries and the one repair attempt (section 5)."""

import json
import time
from dataclasses import dataclass, field
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)
from tenacity.wait import WaitBaseT

from app.llm.base import ChatMessage, LLMError, LLMProvider, LLMResponse, LLMTransientError
from app.llm.prompts import triage_v4
from app.llm.prompts.triage_v4 import RouteInfo

PROMPT_VERSION = triage_v4.PROMPT_VERSION
MAX_ATTEMPTS = 3
DEFAULT_WAIT: WaitBaseT = wait_exponential(multiplier=1, min=1, max=8)

Text = Annotated[str, StringConstraints(strip_whitespace=True)]


class TriageResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    category: Literal[
        "ACCESS",
        "BILLING",
        "BUG",
        "DATABASE",
        "FEATURE_REQUEST",
        "HARDWARE",
        "HR_POLICY",
        "INFRASTRUCTURE",
        "PAYROLL",
        "OTHER",
    ]
    severity: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]
    sentiment: Literal["FRUSTRATED", "NEUTRAL", "POSITIVE"]
    summary: Annotated[Text, Field(min_length=1, max_length=400)]
    suggested_skills: list[Annotated[Text, Field(max_length=40)]] = Field(max_length=5)
    can_self_serve: bool
    draft_response: Annotated[Text, Field(max_length=1500)] | None = None
    confidence: int = Field(ge=0, le=100)
    reasoning: Annotated[Text, Field(max_length=300)]


@dataclass
class ModelOutcome:
    """Everything the triage log needs, whether or not the model produced a usable answer."""

    result: TriageResult | None
    provider: str
    model: str
    latency_ms: int
    raw_text: str | None = None
    error: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    attempts: int = 0
    calls: list[str] = field(default_factory=list)

    @property
    def raw_output(self) -> dict[str, Any] | None:
        return None if self.raw_text is None else {"text": self.raw_text}


def parse_result(text: str) -> TriageResult:
    """Strict parse: one JSON object matching the schema. Raises ValueError otherwise."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"not valid JSON ({exc.msg})") from exc
    if not isinstance(data, dict):
        raise ValueError("expected a JSON object")
    try:
        return TriageResult.model_validate(data)
    except ValidationError as exc:
        problems = "; ".join(
            f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()[:5]
        )
        raise ValueError(problems) from exc


async def run_triage_model(
    provider: LLMProvider,
    title: str,
    description: str,
    routes: list[RouteInfo],
    *,
    wait: WaitBaseT = DEFAULT_WAIT,
    attempts: int = MAX_ATTEMPTS,
) -> ModelOutcome:
    """Ask the model, retrying transient failures, and repair one malformed reply."""
    messages = triage_v4.build_messages(title, description, routes)
    outcome = ModelOutcome(result=None, provider=provider.name, model=provider.model, latency_ms=0)
    start = time.perf_counter()

    async def call(conversation: list[ChatMessage]) -> LLMResponse:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(attempts),
            wait=wait,
            retry=retry_if_exception_type(LLMTransientError),
            reraise=True,
        ):
            with attempt:
                outcome.attempts += 1
                response = await provider.complete_json(
                    conversation, max_tokens=triage_v4.MAX_OUTPUT_TOKENS
                )
        outcome.model = response.model
        outcome.input_tokens += response.input_tokens or 0
        outcome.output_tokens += response.output_tokens or 0
        outcome.raw_text = response.text
        return response

    try:
        first = await call(messages)
        try:
            outcome.result = parse_result(first.text)
        except ValueError as problem:
            # One repair attempt: show the model its reply and what was wrong with it.
            repair = [
                *messages,
                ChatMessage("assistant", first.text[:2000]),
                ChatMessage(
                    "user",
                    f"That reply is invalid: {problem}. Reply again with only the corrected "
                    "JSON object, using exactly the keys and allowed values listed.",
                ),
            ]
            second = await call(repair)
            try:
                outcome.result = parse_result(second.text)
            except ValueError as still_wrong:
                outcome.error = f"invalid output after repair: {still_wrong}"
    except LLMError as exc:
        outcome.error = f"{type(exc).__name__}: {exc}"

    outcome.latency_ms = round((time.perf_counter() - start) * 1000)
    return outcome
