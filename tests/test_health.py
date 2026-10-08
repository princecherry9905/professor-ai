"""Health, config and web page endpoints."""

from app.api.dependencies import get_provider
from app.main import app
from tests.conftest import FakeProvider


def test_health_connected(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"
    assert res.json()["gemini"] == "connected"


def test_health_not_configured(client):
    app.dependency_overrides[get_provider] = lambda: FakeProvider(configured=False)
    assert client.get("/api/health").json()["gemini"] == "not_configured"


def test_health_reports_auth_error(client, fake):
    fake.auth_failed = True
    assert client.get("/api/health").json()["gemini"] == "error"


def test_config_lists_subjects_and_modes_without_secrets(client):
    data = client.get("/api/config").json()
    subject_ids = {s["id"] for s in data["subjects"]}
    mode_ids = {m["id"] for m in data["modes"]}
    assert {"dsa", "os", "dbms", "cn", "oop", "javascript", "python", "ai", "ml", "webdev", "se"} <= subject_ids
    assert mode_ids == {"normal", "one_word", "short", "detailed", "json", "professor", "quiz"}
    assert "key" not in str(data).lower()


def test_index_page_served(client):
    res = client.get("/")
    assert res.status_code == 200
    assert "ProfessorAI" in res.text
    assert client.get("/static/js/app.js").status_code == 200
    assert client.get("/static/css/styles.css").status_code == 200


def test_unknown_route_returns_error_shape(client):
    res = client.get("/api/nope")
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "NOT_FOUND"
