from app.core.config import Settings
from app.llm.base import LLMProvider
from app.llm.groq_provider import GroqProvider


def build_provider(settings: Settings) -> LLMProvider:
    """The configured provider. The worker refuses to start without its API key."""
    if settings.groq_api_key is None or not settings.groq_api_key.get_secret_value():
        raise RuntimeError("GROQ_API_KEY is required to run the triage worker")
    return GroqProvider(settings.groq_api_key.get_secret_value(), settings.llm_model)
