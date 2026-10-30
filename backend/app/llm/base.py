from dataclasses import dataclass
from typing import Literal, Protocol


@dataclass(frozen=True)
class ChatMessage:
    role: Literal["system", "user", "assistant"]
    content: str


@dataclass(frozen=True)
class LLMResponse:
    text: str
    provider: str
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None


class LLMError(Exception):
    """Any failure talking to the model provider."""


class LLMTransientError(LLMError):
    """Timeouts, rate limits and 5xx: worth retrying with backoff."""


class LLMProvider(Protocol):
    """The only way the app talks to a model. Swap Groq for another vendor behind this."""

    name: str
    model: str

    async def complete_json(self, messages: list[ChatMessage], max_tokens: int) -> LLMResponse:
        """Return the model's reply, which the provider asks to be a single JSON object."""
        ...
