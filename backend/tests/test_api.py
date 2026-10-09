import pytest
from fastapi.testclient import TestClient

from app.core.registry import CapabilityRegistry
from app.main import create_app
from app.schemas import CapabilityResult, RunEvent, RunStatus


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/t.db")
    return TestClient(create_app(run_inline=True))


class DummyCapability:
    id = "dummy"

    def run(self, run_id, params, emit):
        emit(RunEvent(run_id=run_id, step="write", status="progress", detail="working"))
        return CapabilityResult(
            run_id=run_id,
            capability_id="dummy",
            status=RunStatus.finished,
            report_markdown=params["question"],
        )


def test_healthz_reports_providers_not_secrets(tmp_path, monkeypatch):
    # Env must be set *before* create_app so the key would leak if the endpoint did.
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/t.db")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-secret")
    client = TestClient(create_app(run_inline=True))
    body = client.get("/healthz").json()
    assert "llm_provider" in body and "search_providers" in body
    assert "sk-secret" not in str(body)


def test_unknown_capability_404(client):
    resp = client.post("/api/runs", json={"capability": "nope", "question": "a valid question"})
    assert resp.status_code == 404


def test_runs_history_is_list(client):
    assert isinstance(client.get("/api/runs").json(), list)


def test_dummy_capability_runs_streams_and_persists(tmp_path, monkeypatch):
    # Review Focus #6 at the API boundary: a capability injected via the registry
    # runs, streams, and persists with no core edits.
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/t.db")
    caps = CapabilityRegistry()
    caps.register("dummy", DummyCapability)
    client = TestClient(create_app(registry=caps, run_inline=True))

    posted = client.post("/api/runs", json={"capability": "dummy", "question": "hello"})
    assert posted.status_code == 202
    run_id = posted.json()["run_id"]

    with client.stream("GET", f"/api/runs/{run_id}/stream") as response:
        first = "".join(response.iter_text())
    assert "event: write" in first and "event: result" in first

    # A reconnect (second stream) must not hang once the live queue is drained.
    with client.stream("GET", f"/api/runs/{run_id}/stream") as response:
        second = "".join(response.iter_text())
    assert "event: result" in second

    result = client.get(f"/api/runs/{run_id}").json()
    assert result["status"] == "finished" and result["report_markdown"] == "hello"
    assert "dummy" in client.get("/healthz").json()["capabilities"]
