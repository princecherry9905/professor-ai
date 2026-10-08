"""Google Gemini implementation of LLMProvider.

This is the ONLY file in the app that imports the google-genai SDK.
"""

import asyncio
import logging
from typing import Optional

import httpx
from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from app.config.settings import Settings
from app.providers.base import (
    ApiKeyMissingError,
    AuthError,
    GenerationConfig,
    LLMProvider,
    Message,
    ProviderError,
    ProviderTimeout,
    ProviderUnavailable,
    RateLimitError,
)

logger = logging.getLogger(__name__)

# Our roles -> Gemini roles
_ROLE_MAP = {"student": "user", "professor": "model"}


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: Optional[genai.Client] = None
        if settings.has_api_key:
            timeout_ms = int(settings.request_timeout_seconds * 1000)
            self._client = genai.Client(
                api_key=settings.gemini_api_key.get_secret_value(),  # type: ignore[union-attr]
                http_options=types.HttpOptions(timeout=timeout_ms),
            )

    @property
    def is_configured(self) -> bool:
        return self._client is not None

    async def generate(self, system: str, messages: list[Message], config: GenerationConfig) -> str:
        if self._client is None:
            raise ApiKeyMissingError("GEMINI_API_KEY is not set")

        try:
            return await self._call_once(system, messages, config)
        except (RateLimitError, ProviderTimeout, ProviderUnavailable) as first_error:
            # One automatic retry for transient problems (never for auth errors).
            logger.warning("Gemini transient error, retrying once: %s", type(first_error).__name__)
            await asyncio.sleep(1.0)
            return await self._call_once(system, messages, config)

    async def _call_once(self, system: str, messages: list[Message], config: GenerationConfig) -> str:
        assert self._client is not None
        contents = [
            types.Content(role=_ROLE_MAP[m.role], parts=[types.Part(text=m.text)]) for m in messages
        ]
        gen_config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=config.temperature,
            max_output_tokens=config.max_output_tokens,
        )
        if config.json_schema is not None:
            gen_config.response_mime_type = "application/json"
            gen_config.response_json_schema = config.json_schema

        try:
            response = await asyncio.wait_for(
                self._client.aio.models.generate_content(
                    model=self._settings.gemini_model, contents=contents, config=gen_config
                ),
                timeout=self._settings.request_timeout_seconds + 5,
            )
        except Exception as exc:  # map every SDK/network failure to our own error types
            mapped = _map_error(exc)
            self.auth_failed = isinstance(mapped, AuthError)
            raise mapped from exc

        self.auth_failed = False

        text = response.text or ""
        if not text.strip():
            raise ProviderUnavailable("Gemini returned an empty response")
        return text


def _map_error(exc: Exception) -> ProviderError:
    if isinstance(exc, ProviderError):
        return exc
    if isinstance(exc, (asyncio.TimeoutError, httpx.TimeoutException)):
        return ProviderTimeout(str(exc))
    if isinstance(exc, genai_errors.APIError):
        code = getattr(exc, "code", None)
        message = str(exc)
        if code in (401, 403) or (code == 400 and "API key" in message):
            return AuthError("Gemini rejected the API key")
        if code == 429:
            return RateLimitError("Gemini rate limit reached")
        if code in (408, 504):
            return ProviderTimeout(message)
        return ProviderUnavailable(f"Gemini API error {code}")
    if isinstance(exc, httpx.HTTPError):
        return ProviderUnavailable("Network error talking to Gemini")
    return ProviderUnavailable(f"Unexpected Gemini failure: {type(exc).__name__}")
