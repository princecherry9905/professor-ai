"""GeminiProvider error mapping and retry, with the SDK client mocked out."""

import asyncio
from types import SimpleNamespace

import httpx
import pytest
from google.genai import errors as genai_errors

from app.config.settings import Settings
from app.providers import gemini_provider
from app.providers.base import (
    ApiKeyMissingError,
    AuthError,
    GenerationConfig,
    Message,
    ProviderTimeout,
    ProviderUnavailable,
    RateLimitError,
)
from app.providers.gemini_provider import GeminiProvider, _map_error


def api_error(cls, code, message="error"):
    return cls(code, {"error": {"code": code, "message": message, "status": "X"}})


@pytest.mark.parametrize(
    "exc, expected",
    [
        (api_error(genai_errors.ClientError, 400, "API key not valid. Please pass a valid API key."), AuthError),
        (api_error(genai_errors.ClientError, 403), AuthError),
        (api_error(genai_errors.ClientError, 429), RateLimitError),
        (api_error(genai_errors.ServerError, 500), ProviderUnavailable),
        (api_error(genai_errors.ServerError, 504), ProviderTimeout),
        (api_error(genai_errors.ClientError, 400, "bad request"), ProviderUnavailable),
        (asyncio.TimeoutError(), ProviderTimeout),
        (httpx.ReadTimeout("slow"), ProviderTimeout),
        (httpx.ConnectError("no network"), ProviderUnavailable),
        (ValueError("weird"), ProviderUnavailable),
    ],
)
def test_error_mapping(exc, expected):
    assert isinstance(_map_error(exc), expected)


class FakeResponse:
    def __init__(self, text):
        self.text = text


class FakeModels:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    async def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return FakeResponse(outcome)


def make_provider(outcomes, monkeypatch):
    monkeypatch.setattr(gemini_provider.asyncio, "sleep", _no_sleep)
    provider = GeminiProvider(Settings(gemini_api_key="test-key", _env_file=None))
    models = FakeModels(outcomes)
    provider._client = SimpleNamespace(aio=SimpleNamespace(models=models))  # type: ignore[assignment]
    return provider, models


async def _no_sleep(_):
    return None


def run(provider, json_schema=None):
    config = GenerationConfig(temperature=0.3, json_schema=json_schema)
    return asyncio.run(provider.generate("system", [Message("student", "hi")], config))


def test_success_and_request_shape(monkeypatch):
    provider, models = make_provider(["Hello student"], monkeypatch)
    assert run(provider, json_schema={"type": "object"}) == "Hello student"
    call = models.calls[0]
    assert call["contents"][0].role == "user"
    assert call["config"].response_mime_type == "application/json"
    assert call["config"].system_instruction == "system"


def test_retries_once_on_transient_error(monkeypatch):
    provider, models = make_provider([api_error(genai_errors.ServerError, 503), "ok"], monkeypatch)
    assert run(provider) == "ok"
    assert len(models.calls) == 2


def test_never_retries_auth_errors(monkeypatch):
    provider, models = make_provider([api_error(genai_errors.ClientError, 403), "ok"], monkeypatch)
    with pytest.raises(AuthError):
        run(provider)
    assert len(models.calls) == 1
    assert provider.auth_failed is True


def test_gives_up_after_second_failure(monkeypatch):
    provider, _ = make_provider([api_error(genai_errors.ClientError, 429)] * 2, monkeypatch)
    with pytest.raises(RateLimitError):
        run(provider)


def test_empty_response_is_unavailable(monkeypatch):
    provider, _ = make_provider(["", ""], monkeypatch)
    with pytest.raises(ProviderUnavailable):
        run(provider)


def test_missing_key_raises():
    provider = GeminiProvider(Settings(gemini_api_key=None, _env_file=None))
    assert provider.is_configured is False
    with pytest.raises(ApiKeyMissingError):
        run(provider)
