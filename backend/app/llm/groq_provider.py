from typing import cast

import groq
from groq import AsyncGroq
from groq.types.chat import ChatCompletionMessageParam
from groq.types.chat.completion_create_params import ResponseFormatResponseFormatJsonObject

from app.llm.base import ChatMessage, LLMError, LLMResponse, LLMTransientError

DEFAULT_MODEL = "llama-3.3-70b-versatile"
TIMEOUT_SECONDS = 15.0


class GroqProvider:
    name = "groq"

    def __init__(self, api_key: str, model: str = DEFAULT_MODEL) -> None:
        self.model = model
        # Retries live in the triage service (tenacity), so the SDK's own are off.
        self._client = AsyncGroq(api_key=api_key, timeout=TIMEOUT_SECONDS, max_retries=0)

    async def complete_json(self, messages: list[ChatMessage], max_tokens: int) -> LLMResponse:
        payload: list[ChatCompletionMessageParam] = [
            cast(ChatCompletionMessageParam, {"role": m.role, "content": m.content})
            for m in messages
        ]
        json_mode: ResponseFormatResponseFormatJsonObject = {"type": "json_object"}
        try:
            completion = await self._client.chat.completions.create(
                model=self.model,
                messages=payload,
                response_format=json_mode,
                temperature=0,
                max_tokens=max_tokens,
            )
        except (
            groq.APITimeoutError,
            groq.APIConnectionError,
            groq.RateLimitError,
            groq.InternalServerError,
        ) as exc:
            raise LLMTransientError(type(exc).__name__) from exc
        except groq.APIStatusError as exc:
            # Groq rejects JSON mode output it cannot parse with a 400; treat it as a bad reply.
            raise LLMError(f"{type(exc).__name__}: status {exc.status_code}") from exc

        choice = completion.choices[0]
        usage = completion.usage
        return LLMResponse(
            text=choice.message.content or "",
            provider=self.name,
            model=completion.model,
            input_tokens=usage.prompt_tokens if usage else None,
            output_tokens=usage.completion_tokens if usage else None,
        )

    async def aclose(self) -> None:
        await self._client.close()
