"""FastAPI dependencies. Tests override get_provider() with a FakeProvider."""

from functools import lru_cache

from fastapi import Depends

from app.config.settings import get_settings
from app.providers.base import LLMProvider
from app.services.tutor_service import TutorService


@lru_cache
def get_provider() -> LLMProvider:
    settings = get_settings()
    if settings.ai_provider == "gemini":
        from app.providers.gemini_provider import GeminiProvider

        return GeminiProvider(settings)
    # Add more providers here, e.g. "openai" or "claude".
    raise ValueError(f"Unknown AI_PROVIDER '{settings.ai_provider}'")


def get_tutor_service(provider: LLMProvider = Depends(get_provider)) -> TutorService:
    return TutorService(provider)
