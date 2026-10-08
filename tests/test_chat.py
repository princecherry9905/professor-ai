"""POST /api/chat — validation, happy path, provider failures."""

import pytest

from app.api.dependencies import get_provider
from app.config.settings import Settings
from app.main import app
from app.providers.base import (
    AuthError,
    ProviderTimeout,
    ProviderUnavailable,
    RateLimitError,
)
from app.providers.gemini_provider import GeminiProvider


def chat(client, **body):
    payload = {"question": "What is binary search?", "subject": "dsa", "mode": "normal"}
    payload.update(body)
    return client.post("/api/chat", json=payload)


# ---- Validation -------------------------------------------------------------

@pytest.mark.parametrize("question", ["", "   ", "\n\t"])
def test_empty_question_rejected(client, question):
    res = chat(client, question=question)
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "empty" in res.json()["error"]["message"].lower()


def test_oversized_question_rejected(client):
    res = chat(client, question="x" * 4001)
    assert res.status_code == 422
    assert "too long" in res.json()["error"]["message"]


def test_unknown_subject_rejected(client):
    assert chat(client, subject="astrology").status_code == 422


def test_unknown_mode_rejected(client):
    assert chat(client, mode="poem").status_code == 422


def test_quiz_mode_not_allowed_on_chat_endpoint(client):
    assert chat(client, mode="quiz").status_code == 422


def test_missing_body_rejected(client):
    assert client.post("/api/chat").status_code == 422


# ---- Happy path -------------------------------------------------------------

def test_chat_normal_returns_markdown(client, fake):
    fake.replies = ["Binary search halves the search space each step."]
    res = chat(client)
    assert res.status_code == 200
    assert res.json() == {
        "answer": "Binary search halves the search space each step.",
        "mode": "normal", "subject": "dsa", "format": "markdown",
    }


def test_subject_and_mode_reach_system_prompt(client, fake):
    fake.replies = ["Normalization reduces redundancy."]
    chat(client, subject="dbms", mode="detailed", question="Explain normalization")
    system = fake.calls[0]["system"]
    assert "DBMS" in system
    assert "## Exam Tip" in system


def test_history_is_sent_and_trimmed(client, fake):
    fake.replies = ["ok"]
    history = [{"role": "student" if i % 2 == 0 else "professor", "text": f"turn {i}"} for i in range(14)]
    assert chat(client, history=history).status_code == 200
    messages = fake.calls[0]["messages"]
    assert len(messages) == 11  # last 10 history turns + the new question
    assert messages[0].text == "turn 4"
    assert messages[-1].role == "student" and messages[-1].text == "What is binary search?"


def test_history_with_bad_role_rejected(client):
    assert chat(client, history=[{"role": "admin", "text": "hi"}]).status_code == 422


# ---- Provider failures ------------------------------------------------------

@pytest.mark.parametrize(
    "error, status, code",
    [
        (AuthError("bad key"), 503, "API_KEY_INVALID"),
        (RateLimitError("429"), 429, "RATE_LIMITED"),
        (ProviderTimeout("slow"), 504, "TIMEOUT"),
        (ProviderUnavailable("down"), 502, "PROVIDER_UNAVAILABLE"),
        (RuntimeError("boom secret-detail"), 500, "INTERNAL_ERROR"),
    ],
)
def test_provider_errors_map_to_friendly_responses(client, fake, error, status, code):
    fake.replies = [error]
    res = chat(client)
    assert res.status_code == status
    body = res.json()
    assert body["error"]["code"] == code
    assert "Traceback" not in res.text
    assert "secret-detail" not in res.text


def test_missing_api_key(client):
    provider = GeminiProvider(Settings(gemini_api_key=None, _env_file=None))
    app.dependency_overrides[get_provider] = lambda: provider
    assert client.get("/api/health").json()["gemini"] == "not_configured"
    res = chat(client)
    assert res.status_code == 503
    assert res.json()["error"]["code"] == "API_KEY_MISSING"
    assert "GEMINI_API_KEY" in res.json()["error"]["message"]


def test_placeholder_key_counts_as_missing():
    assert not Settings(gemini_api_key="your_key_here", _env_file=None).has_api_key
    assert Settings(gemini_api_key="real-looking-key", _env_file=None).has_api_key
