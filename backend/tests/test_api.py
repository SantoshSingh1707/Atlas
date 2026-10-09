import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/t.db")
    return TestClient(create_app(run_inline=True))


def test_healthz_reports_providers_not_secrets(client, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-secret")
    body = client.get("/healthz").json()
    assert "llm_provider" in body and "search_providers" in body
    assert "sk-secret" not in str(body)


def test_unknown_capability_404(client):
    resp = client.post("/api/runs", json={"capability": "nope", "question": "a valid question"})
    assert resp.status_code == 404


def test_runs_history_is_list(client):
    assert isinstance(client.get("/api/runs").json(), list)
