"""Shared test fixtures. A FakeProvider replaces Gemini — no API key or network needed."""

import os

# Make sure a developer's real .env never leaks into the tests.
os.environ["GEMINI_API_KEY"] = ""

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_provider
from app.main import app
from app.providers.base import GenerationConfig, LLMProvider, Message


class FakeProvider(LLMProvider):
    """Returns queued replies (strings) or raises queued exceptions, and records every call."""

    name = "fake"

    def __init__(self, replies: list | None = None, configured: bool = True) -> None:
        self.replies = list(replies or [])
        self.calls: list[dict] = []
        self._configured = configured

    @property
    def is_configured(self) -> bool:
        return self._configured

    async def generate(self, system: str, messages: list[Message], config: GenerationConfig) -> str:
        self.calls.append({"system": system, "messages": messages, "config": config})
        if not self.replies:
            raise AssertionError("FakeProvider ran out of replies")
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


@pytest.fixture
def fake() -> FakeProvider:
    return FakeProvider()


@pytest.fixture
def client(fake: FakeProvider):
    app.dependency_overrides[get_provider] = lambda: fake
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
    app.dependency_overrides.clear()
