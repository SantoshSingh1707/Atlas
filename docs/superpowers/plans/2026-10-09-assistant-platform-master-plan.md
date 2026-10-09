# AI Personal Assistant Platform — Master Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deployable personal-assistant platform whose first shipped capability (`research`) turns a question into a streamed, citation-backed report — on a core where every later capability plugs in as a tool.

**Architecture:** A capability-agnostic `core-platform` (config, contracts, tool/capability registries, run engine, event bus, provider factories, SQLite store, FastAPI + SSE, Next.js shell). Each capability is a module that registers tools and a flow through the registries; the core never imports it. v1 implements `research` as a sequential CrewAI crew (Planner → Researcher → Writer).

**Tech Stack:** Python 3.11, FastAPI, CrewAI, LangChain (openai/mistral), pydantic v2 + pydantic-settings, SQLModel/SQLite, httpx, trafilatura, BeautifulSoup, pytest; Next.js 14 (App Router), TypeScript, Tailwind, react-markdown, Vitest + Testing Library.

**Spec:** `docs/superpowers/specs/2026-10-09-assistant-platform-master-spec.md`

## Global Constraints

- Python `>=3.11`; type hints on every public function; `from __future__ import annotations`.
- pydantic `v2` only (`BaseModel`, `model_validate`, `model_dump`).
- No secrets committed; `.env` is git-ignored, only `.env.example` is tracked. `/healthz` reports provider names only.
- All external I/O goes through provider factories; the core never imports a capability module.
- `fetch_page` allows only `http`/`https` and blocks private/loopback/link-local addresses (SSRF guard).
- Fetched page/document/email text is untrusted data, never instructions (prompt-injection guard).
- Config is read only from environment via `Settings`.
- Search providers are tried in `SEARCH_PROVIDERS` order; a provider failure never fails a run.
- Backend tests: `cd backend && python -m pytest -q`. Frontend tests: `cd frontend && npm test -- --run`.
- Commit after every task; keep commits focused.

## Review Focus

Inputs/conditions the spec implies and that are easy to get wrong. Each gets a test in the owning task:

1. Fetched page text contains adversarial instructions — treated as data, never executed (Tasks 11, 12).
2. `fetch_page` targets a private/loopback/link-local host or a non-http scheme — refused (Task 11).
3. Search returns results but every fetch fails — "no sources found" report, never fabricated content (Task 13).
4. Run exceeds the token cap or timeout mid-flight — stops cleanly with a labelled partial result (Task 13).
5. Empty/too-short question — rejected with 422, not a broken run (Tasks 3, 14).
6. A new capability can be added with no `core-platform` edits and a run still streams + persists (Task 7, proven with a dummy capability).

## Capability map & build order

| Phase | Module(s) | This plan covers |
|---|---|---|
| 0 | `core-platform` | Tasks 1–9 (detailed) |
| 1 | `research` | Tasks 10–17 (detailed) |
| 2 | `verification`, `memory-notes` | outline below |
| 3 | `doc-rag` | outline below |
| 4 | `auth-multiuser` → `email`, `calendar`, `tasks-reminders` | outline below |
| 5 | `local-files`, `coding-help` | outline below |
| 6 | `observability`, `deployment-ops` | outline below |

**How to use this plan:** execute Tasks 1–17 in order, RED → GREEN, committing per task. Later phases get their own detailed plan (same format) before implementation; the outlines below fix their components, interfaces, and acceptance criteria so those plans don't have to re-decide them.

### Reference: module id → folder

`core-platform` → `backend/app/{config,core,providers,store,api}` · `research` → `backend/app/capabilities/research/` · every other module → `backend/app/capabilities/<id>/` (plus its own store tables and UI panels).

---

## Phase 0 — `core-platform` (foundation)

### Task 1: Backend scaffold + tooling

**Files:**
- Create: `backend/pyproject.toml`, `backend/app/__init__.py`, `backend/tests/__init__.py`, `backend/.gitignore`, `.gitignore` (root), `README.md`
- Test: `backend/tests/test_scaffold.py`

**Interfaces:**
- Consumes: nothing.
- Produces: importable `app` package; pytest configured; project metadata with runtime + dev dependencies.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_scaffold.py
import app


def test_app_package_imports():
    assert app is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_scaffold.py -q`
Expected: FAIL (`ModuleNotFoundError: app` / no pyproject).

- [ ] **Step 3: Implement the scaffold**

`backend/pyproject.toml`: `requires-python = ">=3.11"`, `[tool.pytest.ini_options] pythonpath = ["."]`, runtime deps (fastapi, uvicorn[standard], crewai, langchain-openai, langchain-mistralai, pydantic, pydantic-settings, sqlmodel, httpx, requests, trafilatura, beautifulsoup4, ddgs, tavily-python) and `[project.optional-dependencies] dev = ["pytest", "pytest-asyncio", "respx", "ruff"]`. `app/__init__.py` empty. Root `.gitignore`: `.env`, `data/`, `node_modules/`, `.next/`, `__pycache__/`, `.pytest_cache/`, `*.pyc`. `README.md`: one-paragraph project description + local dev and Docker commands.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_scaffold.py -q`
Expected: PASS (1 passed).

- [ ] **Step 5: Commit**

```bash
git add backend .gitignore README.md
git commit -m "chore(core): backend scaffold and tooling"
```

---

### Task 2: Settings (config)

**Files:**
- Create: `backend/app/config/__init__.py`, `backend/app/config/settings.py`
- Test: `backend/tests/test_settings.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `Settings` (pydantic-settings) and cached `get_settings() -> Settings`. Fields: `llm_provider="local"`, `local_llm_base_url="http://localhost:1234/v1"`, `local_llm_model="local-model"`, `openai_api_key=None`, `openai_model="gpt-4o-mini"`, `mistral_api_key=None`, `mistral_model="mistral-large-latest"`, `search_providers=["tavily","duckduckgo"]`, `tavily_api_key=None`, `run_timeout_seconds=300`, `max_tokens_per_run=60000`, `results_per_query=5`, `max_sources_to_read=8`, `database_url="sqlite:///./data/runs.db"`, `cors_origins=["http://localhost:3000"]`, `auth_enabled=False`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_settings.py
from app.config.settings import Settings, get_settings


def test_defaults():
    s = Settings()
    assert s.llm_provider == "local"
    assert s.search_providers == ["tavily", "duckduckgo"]
    assert s.auth_enabled is False


def test_comma_env_parses_to_list(monkeypatch):
    monkeypatch.setenv("SEARCH_PROVIDERS", "duckduckgo,tavily")
    monkeypatch.setenv("MAX_TOKENS_PER_RUN", "1234")
    s = Settings()
    assert s.search_providers == ["duckduckgo", "tavily"]
    assert s.max_tokens_per_run == 1234


def test_get_settings_cached():
    assert get_settings() is get_settings()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_settings.py -q`
Expected: FAIL (`No module named 'app.config.settings'`).

- [ ] **Step 3: Implement `settings.py`**

`Settings(BaseSettings)` with `model_config = SettingsConfigDict(env_file=".env", extra="ignore")` and the fields above. `field_validator(mode="before")` splits the two list fields on `,` and strips. `@lru_cache def get_settings() -> Settings: return Settings()`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_settings.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/config backend/tests/test_settings.py
git commit -m "feat(core): environment-driven settings"
```

---

### Task 3: Domain contracts

**Files:**
- Create: `backend/app/schemas.py`
- Test: `backend/tests/test_schemas.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `RunStatus(str,Enum)`; `SearchResult{title,url,snippet="",provider=""}`; `ResearchOptions{max_sub_queries=5,results_per_query=5,max_sources_to_read=8}`; `ResearchRequest{question:str(min_length=3,max_length=2000),options:ResearchOptions|None=None}`; `RunEvent{run_id,step:Literal["plan","search","read","write","done","error"],status:Literal["started","progress","finished","failed"],detail:str|None=None,token:str|None=None}`; `Citation{index:int,title,url,snippet=""}`; `ResearchPlan{sub_queries:list[str],outline=""}`; `Note{fact,source_url,source_title=""}`; `ResearchNotes{notes:list[Note]}`; `CapabilityResult{run_id,capability_id,status:RunStatus,report_markdown="",citations:list[Citation]=[],sources:list[SearchResult]=[],tokens=0,cost=0.0,duration_ms=0,error:str|None=None}`; `ResearchResult` aliased to `CapabilityResult` for v1.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_schemas.py
import pytest
from pydantic import ValidationError
from app.schemas import ResearchRequest, ResearchOptions, CapabilityResult, RunEvent, RunStatus


def test_options_defaults():
    assert ResearchRequest(question="how do transformers work").options is None
    assert ResearchOptions().max_sub_queries == 5


def test_short_question_rejected():
    with pytest.raises(ValidationError):
        ResearchRequest(question="hi")


def test_result_roundtrip_and_status_enum():
    r = CapabilityResult(run_id="r", capability_id="research", status=RunStatus.finished)
    assert r.citations == []
    assert CapabilityResult.model_validate(r.model_dump()).run_id == "r"


def test_run_event_literal_rejects_unknown_step():
    with pytest.raises(ValidationError):
        RunEvent(run_id="r", step="nope", status="started")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_schemas.py -q`
Expected: FAIL (`No module named 'app.schemas'`).

- [ ] **Step 3: Implement `schemas.py`**

Create the models exactly as listed. Use `from __future__ import annotations`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_schemas.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas.py backend/tests/test_schemas.py
git commit -m "feat(core): shared domain contracts"
```

---

### Task 4: Provider factories (LLM + embeddings stub)

**Files:**
- Create: `backend/app/providers/__init__.py`, `backend/app/providers/llm.py`, `backend/app/providers/embeddings.py`
- Test: `backend/tests/test_llm_factory.py`

**Interfaces:**
- Consumes: `Settings`.
- Produces: `ConfigError(Exception)`; `get_llm(settings) -> BaseChatModel`; `get_embeddings(settings) -> Embeddings` (v1: a `NotImplementedError` stub documenting the `doc-rag` seam).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_llm_factory.py
import pytest
from app.config.settings import Settings
from app.providers.llm import get_llm, ConfigError


def test_local_points_at_base_url():
    llm = get_llm(Settings(llm_provider="local", local_llm_base_url="http://localhost:1234/v1", local_llm_model="m1"))
    assert str(llm.openai_api_base) == "http://localhost:1234/v1"
    assert llm.model_name == "m1"


def test_openai_requires_key():
    with pytest.raises(ConfigError):
        get_llm(Settings(llm_provider="openai", openai_api_key=None))


def test_openai_ok():
    llm = get_llm(Settings(llm_provider="openai", openai_api_key="sk-x", openai_model="gpt-4o-mini"))
    assert llm.model_name == "gpt-4o-mini"


def test_unknown_provider():
    with pytest.raises(ConfigError):
        get_llm(Settings(llm_provider="wat"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_llm_factory.py -q`
Expected: FAIL (`No module named 'app.providers.llm'`).

- [ ] **Step 3: Implement the factories**

`llm.py`: branch on `settings.llm_provider` — `"local"` → `ChatOpenAI(model=local_llm_model, base_url=local_llm_base_url, api_key="not-needed", temperature=0.2)`; `"openai"` → require key else `ConfigError`, `ChatOpenAI(...)`; `"mistral"` → require key else `ConfigError`, `ChatMistralAI(...)`; else `ConfigError`. `embeddings.py`: `get_embeddings(settings)` raises `NotImplementedError("embeddings provider lands with doc-rag")` — the named seam.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_llm_factory.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/providers backend/tests/test_llm_factory.py
git commit -m "feat(core): provider factories"
```

---

### Task 5: Run store (SQLite)

**Files:**
- Create: `backend/app/store/__init__.py`, `backend/app/store/models.py`, `backend/app/store/repository.py`
- Test: `backend/tests/test_store.py`

**Interfaces:**
- Consumes: `RunEvent`, `CapabilityResult`, `Citation`, `SearchResult`, `RunStatus`.
- Produces: SQLModel tables `Run`(id:str pk, capability_id, question, status, report_markdown|None, error|None, tokens, cost, duration_ms, created_at, updated_at); `RunStep`(id:int pk, run_id, step, status, detail|None, created_at); `CitationRow`(id:int pk, run_id, index, title, url, snippet). `RunBundle(BaseModel){run:RunData, steps:list[StepData], citations:list[Citation]}`. `RunStore(database_url)` with `create_run(capability_id, question)->str`, `add_step(event)->None`, `finalize(result)->None`, `fail(run_id,error)->None`, `get_run(run_id)->RunBundle|None`, `list_runs(limit=20,offset=0)->list[RunData]`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_store.py
from app.schemas import CapabilityResult, RunEvent, Citation, SearchResult, RunStatus
from app.store.repository import RunStore


def test_create_and_get():
    s = RunStore("sqlite://")
    rid = s.create_run("research", "what is rag")
    b = s.get_run(rid)
    assert b.run.question == "what is rag"
    assert b.run.status == "pending"


def test_add_step_and_finalize():
    s = RunStore("sqlite://")
    rid = s.create_run("research", "q")
    s.add_step(RunEvent(run_id=rid, step="plan", status="started"))
    s.finalize(CapabilityResult(
        run_id=rid, capability_id="research", status=RunStatus.finished, report_markdown="# R",
        citations=[Citation(index=1, title="t", url="https://x")],
        sources=[SearchResult(title="t", url="https://x")], tokens=10, cost=0.01, duration_ms=5))
    b = s.get_run(rid)
    assert b.run.status == "finished" and len(b.steps) == 1 and b.citations[0].index == 1


def test_list_runs_newest_first():
    s = RunStore("sqlite://")
    a = s.create_run("research", "a"); b = s.create_run("research", "b")
    assert [r.id for r in s.list_runs()] == [b, a]


def test_fail_sets_error():
    s = RunStore("sqlite://")
    rid = s.create_run("research", "q")
    s.fail(rid, "boom")
    assert s.get_run(rid).run.error == "boom"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_store.py -q`
Expected: FAIL (`No module named 'app.store.repository'`).

- [ ] **Step 3: Implement the store**

`models.py`: tables + read models `RunData`, `StepData`. `repository.py`: engine from `database_url` (shared in-memory engine for `sqlite://`), `create_all`, `uuid4().hex` ids. `add_step` inserts a `RunStep`. `finalize` sets fields + `finished` and inserts citations. `fail` sets `failed` + error. `get_run` returns `RunBundle|None`. `list_runs` orders `created_at` desc then id desc.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_store.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/store backend/tests/test_store.py
git commit -m "feat(core): SQLite run store"
```

---

### Task 6: Tool + capability registries (extensibility seam)

**Files:**
- Create: `backend/app/core/__init__.py`, `backend/app/core/registry.py`
- Test: `backend/tests/test_registry.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `Tool` protocol `{name:str, description:str, run(**kwargs)->Any}`; `ToolRegistry` with `register(tool)`, `get(name)->Tool`, `names()->list[str]`; `Capability` protocol `{id:str, run(run_id:str, params:dict, emit:Callable[[RunEvent],None])->CapabilityResult}`; `CapabilityRegistry` with `register(capability_id:str, factory:Callable[[],Capability])`, `create(capability_id)->Capability`, `ids()->list[str]`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_registry.py
import pytest
from app.core.registry import ToolRegistry, CapabilityRegistry


class EchoTool:
    name = "echo"; description = "returns input"
    def run(self, text): return text


def test_tool_registry_roundtrip():
    r = ToolRegistry(); r.register(EchoTool())
    assert r.names() == ["echo"]
    assert r.get("echo").run(text="hi") == "hi"


def test_tool_registry_unknown_raises():
    with pytest.raises(KeyError):
        ToolRegistry().get("nope")


def test_capability_registry_roundtrip():
    r = CapabilityRegistry()
    r.register("dummy", lambda: object())
    assert r.ids() == ["dummy"]
    assert r.create("dummy") is not None


def test_capability_registry_unknown_raises():
    with pytest.raises(KeyError):
        CapabilityRegistry().create("nope")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_registry.py -q`
Expected: FAIL (`No module named 'app.core.registry'`).

- [ ] **Step 3: Implement `registry.py`**

`ToolRegistry` backed by a dict; `register` raises `ValueError` on duplicate names; `get` raises `KeyError` for unknown. `CapabilityRegistry` backed by a dict of factories; `register` raises `ValueError` on duplicate ids; `create` calls the factory fresh each time and raises `KeyError` for unknown.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_registry.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/registry.py backend/app/core/__init__.py backend/tests/test_registry.py
git commit -m "feat(core): tool and capability registries"
```

---

### Task 7: Event bus + run engine (with extensibility proof)

**Files:**
- Create: `backend/app/core/events.py`, `backend/app/core/engine.py`
- Test: `backend/tests/test_engine.py`

**Interfaces:**
- Consumes: `RunStore`, `CapabilityRegistry`, `RunEvent`, `CapabilityResult`, `RunStatus`.
- Produces: `EventBus` with `publish(event)`, `stream(run_id)->Iterator[RunEvent]`, `close(run_id)`; `RunEngine(*, store, bus, capabilities)` with `submit(capability_id, params)->str` (creates the run and returns its id) and `execute(run_id)->CapabilityResult` (synchronous, for tests and inline mode).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_engine.py
from app.core.engine import RunEngine
from app.core.events import EventBus
from app.core.registry import CapabilityRegistry
from app.schemas import CapabilityResult, RunEvent, RunStatus
from app.store.repository import RunStore


class DummyCapability:
    id = "dummy"
    def run(self, run_id, params, emit):
        emit(RunEvent(run_id=run_id, step="write", status="progress", detail="working"))
        return CapabilityResult(run_id=run_id, capability_id="dummy",
                                status=RunStatus.finished, report_markdown=params["question"])


def _engine():
    caps = CapabilityRegistry(); caps.register("dummy", DummyCapability)
    return RunEngine(store=RunStore("sqlite://"), bus=EventBus(), capabilities=caps)


def test_execute_runs_capability_and_finalizes():
    e = _engine()
    rid = e.submit("dummy", {"question": "hello"})
    result = e.execute(rid)
    assert result.status == RunStatus.finished
    assert result.report_markdown == "hello"
    assert e.store.get_run(rid).run.status == "finished"
    assert [s.step for s in e.store.get_run(rid).steps] == ["write"]


def test_stream_yields_published_events_then_closes():
    e = _engine()
    rid = e.submit("dummy", {"question": "hi"})
    e.execute(rid)
    events = list(e.bus.stream(rid))
    assert events and events[-1].step in {"done", "error"}


def test_unknown_capability_raises():
    e = _engine()
    try:
        e.submit("nope", {})
        assert False, "expected KeyError"
    except KeyError:
        pass
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_engine.py -q`
Expected: FAIL (`No module named 'app.core.engine'`).

- [ ] **Step 3: Implement `events.py` and `engine.py`**

`EventBus`: per-run `queue.Queue` (bounded); `publish` appends; `stream` yields until a terminal event (`step in {"done","error"}`), then closes. `RunEngine`: `submit` creates a run via `store.create_run(capability_id, params.get("question",""))`, returns the id. `execute(run_id)` looks up the run's capability id, builds the capability from the registry, calls `capability.run(run_id, params, emit)` where `emit` publishes to the bus and `store.add_step(event)`; on success `store.finalize(result)` and publishes a terminal `done/finished`; on exception `store.fail(run_id, str(exc))`, publishes `error/failed`, and returns a failed `CapabilityResult`. This proves Review Focus #6: a capability added via the registry runs, streams, and persists with **no core edits**.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_engine.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/events.py backend/app/core/engine.py backend/tests/test_engine.py
git commit -m "feat(core): event bus and run engine"
```

---

### Task 8: API shell + SSE

**Files:**
- Create: `backend/app/api/__init__.py`, `backend/app/api/routes.py`, `backend/app/main.py`
- Test: `backend/tests/test_api.py`

**Interfaces:**
- Consumes: `get_settings`, `RunStore`, `EventBus`, `RunEngine`, `CapabilityRegistry`.
- Produces: `create_app(registry=None, run_inline=False) -> FastAPI` exposing `POST /api/runs`, `GET /api/runs/{run_id}/stream`, `GET /api/runs/{run_id}`, `GET /api/runs`, `GET /healthz`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_api.py
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
    assert client.post("/api/runs", json={"capability": "nope", "question": "a valid question"}).status_code == 404


def test_runs_history_is_list(client):
    assert isinstance(client.get("/api/runs").json(), list)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_api.py -q`
Expected: FAIL (`No module named 'app.main'`).

- [ ] **Step 3: Implement the API**

`routes.py`: a `GET /healthz` returning `{"status":"ok","llm_provider":settings.llm_provider,"search_providers":settings.search_providers}` (names only). `POST /api/runs` body `{capability:str, question:str, options?:dict}`; validate question (min 3) → 422 otherwise; 404 unknown capability; else `engine.submit(...)` → `202 {"run_id":rid}`. `GET /api/runs/{id}/stream` → `StreamingResponse(media_type="text/event-stream")` emitting `event: <step>` + `data: <RunEvent json>` then a final `event: result`. `GET /api/runs/{id}` → stored result or 404; `GET /api/runs` → history list. `main.py`: `create_app(registry=None, run_inline=False)` builds defaults (settings, store, bus, engine, empty registry unless passed), adds `CORSMiddleware` from `cors_origins`, ensures `data/` exists; executes runs inline when `run_inline` else in a background thread. `run_inline` is a test/DI flag only, never client-controlled. This task includes the capability-isolation wiring: the app holds a `CapabilityRegistry` and knows nothing about any concrete capability.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_api.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/api backend/app/main.py backend/tests/test_api.py
git commit -m "feat(core): API shell with SSE and capability dispatch"
```

---

### Task 9: Frontend scaffold + typed API/SSE client

**Files:**
- Create: `frontend/package.json`, `frontend/tsconfig.json`, `frontend/next.config.mjs`, `frontend/tailwind.config.ts`, `frontend/postcss.config.mjs`, `frontend/.gitignore`, `frontend/vitest.config.ts`, `frontend/test/setup.ts`
- Create: `frontend/app/layout.tsx`, `frontend/app/globals.css`, `frontend/app/page.tsx`
- Create: `frontend/lib/types.ts`, `frontend/lib/api.ts`
- Test: `frontend/test/api.test.ts`

**Interfaces:**
- Consumes: backend REST + SSE.
- Produces: TS types mirroring the backend (`RunEvent`, `Citation`, `CapabilityResult`, `RunSummary`); `API_BASE` from `NEXT_PUBLIC_API_BASE_URL` (default `http://localhost:8000`); `startRun(capability, question):Promise<{run_id:string}>`; `getResult(runId):Promise<CapabilityResult>`; `listRuns():Promise<RunSummary[]>`; `streamRun(runId, handlers, eventSourceFactory?): EventSource`.

- [ ] **Step 1: Write the failing test**

```ts
// frontend/test/api.test.ts
import { describe, it, expect, vi } from "vitest";
import { startRun, getResult } from "@/lib/api";

describe("api client", () => {
  it("posts capability + question and returns run_id", async () => {
    const f = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ run_id: "r1" }) });
    vi.stubGlobal("fetch", f);
    const out = await startRun("research", "hello");
    expect(out.run_id).toBe("r1");
    const [url, init] = f.mock.calls[0];
    expect(url).toContain("/api/runs");
    expect(JSON.parse(init.body)).toEqual({ capability: "research", question: "hello" });
  });

  it("throws on non-ok response", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 500, text: async () => "boom" }));
    await expect(getResult("r1")).rejects.toThrow();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm install && npm test -- --run`
Expected: FAIL (cannot resolve `@/lib/api`).

- [ ] **Step 3: Implement scaffold + client**

`package.json` deps: next@14, react@18, react-dom@18, react-markdown, remark-gfm, clsx; dev: typescript, @types/react, @types/node, tailwindcss, postcss, autoprefixer, vitest, @testing-library/react, @testing-library/jest-dom, jsdom; scripts `dev/build/start/test/lint`. `vitest.config.ts`: jsdom env, `@` alias, setup file. `lib/api.ts`: `fetch` for REST, `EventSource` for `streamRun` (injectable factory). `app/page.tsx`: placeholder shell; `layout.tsx` sets metadata + dark theme; `globals.css` sets base theme.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm test -- --run`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add frontend
git commit -m "feat(core): frontend shell and typed API client"
```

---

## Phase 1 — `research` (v1 anchor)

### Task 10: Search providers + fallback chain

**Files:**
- Create: `backend/app/providers/search/__init__.py`, `base.py`, `tavily.py`, `duckduckgo.py`, `chain.py`
- Test: `backend/tests/test_search_chain.py`

**Interfaces:**
- Consumes: `Settings`, `SearchResult`.
- Produces: `SearchError(Exception)`; `SearchProvider(Protocol){name:str; search(query:str,k:int)->list[SearchResult]}`; `TavilyProvider(api_key:str)`; `DuckDuckGoProvider()`; `get_search_chain(settings)->list[SearchProvider]`; `SearchChain(providers)` with `.search(query,k)->list[SearchResult]` and `.names->list[str]`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_search_chain.py
import pytest
from app.schemas import SearchResult
from app.providers.search.chain import SearchChain
from app.providers.search.base import SearchError


class FakeProvider:
    def __init__(self, name, results=None, error=None):
        self.name, self._r, self._e = name, results or [], error
    def search(self, query, k):
        if self._e: raise SearchError(self._e)
        return self._r


def _r(t): return SearchResult(title=t, url=f"https://x/{t}", provider="fake")


def test_first_non_empty_wins():
    assert SearchChain([FakeProvider("a", [_r("a1")]), FakeProvider("b", [_r("b1")])]).search("q", 5)[0].title == "a1"


def test_falls_back_on_error():
    assert SearchChain([FakeProvider("a", error="boom"), FakeProvider("b", [_r("b1")])]).search("q", 5)[0].title == "b1"


def test_falls_back_on_empty():
    assert SearchChain([FakeProvider("a", []), FakeProvider("b", [_r("b1")])]).search("q", 5)[0].title == "b1"


def test_all_fail_raises():
    with pytest.raises(SearchError):
        SearchChain([FakeProvider("a", error="x"), FakeProvider("b", error="y")]).search("q", 5)


def test_all_empty_returns_empty():
    assert SearchChain([FakeProvider("a", []), FakeProvider("b", [])]).search("q", 5) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_search_chain.py -q`
Expected: FAIL (`No module named 'app.providers.search'`).

- [ ] **Step 3: Implement the search package**

`chain.py`: iterate providers, catch `Exception`, keep the last error, return the first non-empty list; if none non-empty and an error occurred, raise `SearchError` with joined messages; else `[]`. `tavily.py`: wrap `tavily.TavilyClient(api_key).search(...)`. `duckduckgo.py`: wrap `ddgs.DDGS().text(...)`. Both map to `SearchResult` and wrap failures in `SearchError`. `get_search_chain` maps `settings.search_providers` names to constructors, `ValueError` on unknown.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_search_chain.py -q`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/providers/search backend/tests/test_search_chain.py
git commit -m "feat(research): pluggable search with fallback"
```

---

### Task 11: Page fetcher with SSRF guard

**Files:**
- Create: `backend/app/capabilities/__init__.py`, `backend/app/capabilities/research/__init__.py`, `backend/app/capabilities/research/fetch_page.py`
- Test: `backend/tests/test_fetch_page.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `FetchError(Exception)`; `PageContent` dataclass `{url,title,text}`; `is_safe_url(url)->bool`; `fetch_page(url,*,timeout=15.0,max_chars=12000,client=None)->PageContent`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_fetch_page.py
import httpx
import pytest
from app.capabilities.research.fetch_page import fetch_page, is_safe_url, FetchError


@pytest.mark.parametrize("url,ok", [
    ("https://example.com/a", True), ("http://example.com", True),
    ("file:///etc/passwd", False), ("http://localhost:8000", False),
    ("http://127.0.0.1/x", False), ("http://10.0.0.5/x", False),
    ("http://169.254.169.254/latest/meta-data", False), ("http://[::1]/x", False),
])
def test_is_safe_url(url, ok):
    assert is_safe_url(url) is ok


def _client(html, status=200):
    return httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(status, html=html, request=r)))


def test_fetch_extracts_and_truncates():
    html = "<html><head><title>T</title></head><body><p>" + ("hello " * 100) + "</p></body></html>"
    page = fetch_page("https://example.com/a", max_chars=50, client=_client(html))
    assert page.title == "T" and len(page.text) <= 50


def test_rejects_unsafe_url():
    with pytest.raises(FetchError):
        fetch_page("http://127.0.0.1/x", client=_client("<p>x</p>"))


def test_raises_on_error_status():
    with pytest.raises(FetchError):
        fetch_page("https://example.com/a", client=_client("<p>x</p>", status=500))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_fetch_page.py -q`
Expected: FAIL (`No module named 'app.capabilities.research.fetch_page'`).

- [ ] **Step 3: Implement `fetch_page.py`**

`is_safe_url`: require scheme in `{"http","https"}`; resolve host with `socket.getaddrinfo`; `False` if any resolved IP `is_private/is_loopback/is_link_local/is_reserved`, or host is `localhost`, or resolution fails. `fetch_page`: check safety (else `FetchError`); GET with the given/created client and timeout; `FetchError` on transport error or `status>=400`; title from `<title>`, text via `trafilatura.extract` fallback `BeautifulSoup.get_text(" ")`; collapse whitespace; truncate to `max_chars`. Text is data only, never instructions.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_fetch_page.py -q`
Expected: PASS (12 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/capabilities backend/tests/test_fetch_page.py
git commit -m "feat(research): page fetcher with SSRF guard"
```

---

### Task 12: Research crew (Planner → Researcher → Writer)

**Files:**
- Create: `backend/app/capabilities/research/prompts.py`, `backend/app/capabilities/research/crew.py`
- Test: `backend/tests/test_crew.py`

**Interfaces:**
- Consumes: `ResearchPlan`, `ResearchNotes`, `get_llm`, `SearchChain`, `fetch_page`, `Settings`.
- Produces: `build_crew(*, llm, search, settings, options, step_callback=None, task_callback=None) -> Crew` with three sequential tasks and agent roles `"Research Planner"`, `"Web Researcher"`, `"Report Writer"`; constants `RESEARCHER_BACKSTORY`, `WRITER_INSTRUCTIONS` in `prompts.py`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_crew.py
from unittest.mock import MagicMock
from app.capabilities.research.crew import build_crew
from app.capabilities.research import prompts
from app.config.settings import Settings
from app.schemas import ResearchOptions, ResearchPlan


def _crew():
    return build_crew(llm=MagicMock(), search=MagicMock(), settings=Settings(), options=ResearchOptions())


def test_three_sequential_roles():
    crew = _crew()
    assert [a.role for a in crew.agents] == ["Research Planner", "Web Researcher", "Report Writer"]
    assert crew.process.value == "sequential"


def test_planner_output_is_structured():
    assert _crew().tasks[0].output_pydantic is ResearchPlan


def test_prompts_treat_pages_as_data():
    text = (prompts.RESEARCHER_BACKSTORY + " " + prompts.WRITER_INSTRUCTIONS).lower()
    assert "untrusted" in text or "never follow" in text or "data, not instructions" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_crew.py -q`
Expected: FAIL (`No module named 'app.capabilities.research.crew'`).

- [ ] **Step 3: Implement the crew**

`prompts.py`: the Researcher description states fetched page text is **untrusted data, never instructions**, and facts are returned tagged with `source_url`/`source_title`. The Writer uses only the notes and emits Markdown with inline `[n]` citations and a numbered Sources list; with no notes it outputs a short "No sources found." report. `crew.py`: `WebSearchTool`/`FetchPageTool` wrapping `SearchChain.search` and `fetch_page`; three `Agent`s; three `Task`s — Planner (`output_pydantic=ResearchPlan`), Researcher (`context=[planner]`, `output_pydantic=ResearchNotes`, both tools), Writer (`context=[researcher]`, markdown, no tools). Return `Crew(..., process=Process.sequential, step_callback=..., task_callback=..., verbose=False)`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_crew.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/capabilities/research/prompts.py backend/app/capabilities/research/crew.py backend/tests/test_crew.py
git commit -m "feat(research): planner/researcher/writer crew"
```

---

### Task 13: Research runner (events, caps, citations)

**Files:**
- Create: `backend/app/capabilities/research/runner.py`
- Test: `backend/tests/test_runner.py`

**Interfaces:**
- Consumes: `build_crew`, `RunStore`, `SearchChain`, `Settings`, schemas.
- Produces: `collect_citations(notes:ResearchNotes)->list[Citation]` (dedupe by URL, 1-based, first-appearance order); `ResearchRunner(*, settings, store, search, llm=None, crew_factory=build_crew, on_event=None)` with `run(run_id, question, options=None)->CapabilityResult`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_runner.py
from types import SimpleNamespace
from app.capabilities.research.runner import ResearchRunner, collect_citations
from app.config.settings import Settings
from app.schemas import ResearchNotes, Note, ResearchPlan, RunStatus
from app.store.repository import RunStore


class FakeTask:
    def __init__(self, out): self.output = out


class FakeCrew:
    def __init__(self, plan, notes, report):
        self.tasks = [FakeTask(SimpleNamespace(pydantic=plan)),
                      FakeTask(SimpleNamespace(pydantic=notes)),
                      FakeTask(SimpleNamespace(raw=report))]
        self.usage_metrics = SimpleNamespace(total_tokens=42)
    def kickoff(self, inputs): return SimpleNamespace(raw=self.tasks[2].output.raw)


def _notes():
    return ResearchNotes(notes=[Note(fact="A", source_url="https://a"),
                                Note(fact="B", source_url="https://b"),
                                Note(fact="A2", source_url="https://a")])


def test_collect_citations_dedupes():
    c = collect_citations(_notes())
    assert [x.url for x in c] == ["https://a", "https://b"] and [x.index for x in c] == [1, 2]


def test_run_emits_ordered_events_and_finalizes():
    events = []; store = RunStore("sqlite://"); rid = store.create_run("research", "q")
    crew = FakeCrew(ResearchPlan(sub_queries=["a"]), _notes(), "# R [1] [2]")
    runner = ResearchRunner(settings=Settings(), store=store, search=None,
                            crew_factory=lambda **kw: crew, on_event=events.append)
    result = runner.run(rid, "q")
    steps = [e.step for e in events]
    assert steps[0] == "plan" and steps[-1] == "done"
    assert result.tokens == 42 and store.get_run(rid).run.status == "finished"
    assert [c.index for c in result.citations] == [1, 2]


def test_no_sources_fails_soft():
    events = []; store = RunStore("sqlite://"); rid = store.create_run("research", "q")
    crew = FakeCrew(ResearchPlan(sub_queries=[]), ResearchNotes(notes=[]), "No sources found.")
    runner = ResearchRunner(settings=Settings(), store=store, search=None,
                            crew_factory=lambda **kw: crew, on_event=events.append)
    result = runner.run(rid, "q")
    assert "No sources found" in result.report_markdown and result.citations == []


def test_exception_marks_run_failed():
    events = []; store = RunStore("sqlite://"); rid = store.create_run("research", "q")
    def boom(**kw): raise RuntimeError("llm down")
    runner = ResearchRunner(settings=Settings(), store=store, search=None,
                            crew_factory=boom, on_event=events.append)
    result = runner.run(rid, "q")
    assert events[-1].step == "error" and store.get_run(rid).run.status == "failed"
    assert result.report_markdown == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_runner.py -q`
Expected: FAIL (`No module named 'app.capabilities.research.runner'`).

- [ ] **Step 3: Implement `runner.py`**

`collect_citations`: first occurrence per URL wins, assign `1..n`, carry title/snippet. `ResearchRunner.run`: time the run; `emit(event)` calls `on_event` and `store.add_step`; emit `plan/started`; build the crew via `crew_factory(llm=self.llm or get_llm(settings), search=search, settings=settings, options=options or ResearchOptions(), step_callback=..., task_callback=...)`; `crew.kickoff(inputs={"question": question})`; read the planner `ResearchPlan`, researcher `ResearchNotes`, writer markdown from `crew.tasks[...]`. Read `crew.usage_metrics.total_tokens`; if over `max_tokens_per_run` or elapsed over `run_timeout_seconds`, emit `error/progress` detail `"cap reached; returning partial report"` and keep the partial report. Build the `CapabilityResult(capability_id="research", ...)` with `collect_citations`, flattened sources, tokens, duration; `store.finalize`; emit `done/finished`; return. On any exception: `store.fail`, emit `error/failed`, return an empty-report failed result.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_runner.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/capabilities/research/runner.py backend/tests/test_runner.py
git commit -m "feat(research): research runner with events and caps"
```

---

### Task 14: Research capability registration + API wiring

**Files:**
- Create: `backend/app/capabilities/research/capability.py`, `backend/app/capabilities/research/register.py`
- Modify: `backend/app/main.py` (load registered capabilities)
- Test: `backend/tests/test_research_api.py`

**Interfaces:**
- Consumes: `ResearchRunner`, `CapabilityResult`, `CapabilityRegistry`.
- Produces: `ResearchCapability` implementing the `Capability` protocol (`id="research"`); `register(registry:CapabilityRegistry)->None`; `create_app()` wires research without the core importing it (the app calls `register`).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_research_api.py
import pytest
from fastapi.testclient import TestClient
from app.main import create_app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/t.db")
    monkeypatch.setenv("LLM_PROVIDER", "local")
    app = create_app(run_inline=True)
    # replace the crew factory with a fake so tests stay offline
    fake = pytest.MonkeyPatch()
    return TestClient(app)


def test_research_appears_in_capabilities(client):
    assert "research" in client.get("/healthz").json()["capabilities"]


def test_short_question_422(client):
    assert client.post("/api/runs", json={"capability": "research", "question": "hi"}).status_code == 422
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_research_api.py -q`
Expected: FAIL (`research` not in capabilities / route gap).

- [ ] **Step 3: Implement registration + wire `main.py`**

`capability.py`: `ResearchCapability` holds settings/search/llm and a `crew_factory` (injectable for tests), and its `run(run_id, params, emit)` delegates to `ResearchRunner(...).run(...)`. `register.py`: `register(registry)` calls `registry.register("research", lambda: ResearchCapability.from_settings(...))`. `main.py`: build the registry, call the research module's `register` (the only place the core references a capability, and only by calling its registration entrypoint), extend `/healthz` with `"capabilities": registry.ids()`. Keep `create_app(registry=None)` so a caller can supply their own registry (used to prove isolation in Task 7).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_research_api.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/capabilities/research backend/app/main.py backend/tests/test_research_api.py
git commit -m "feat(research): register capability with the core"
```

---

### Task 15: Composer + live progress UI

**Files:**
- Create: `frontend/components/Composer.tsx`, `frontend/components/ProgressList.tsx`
- Modify: `frontend/app/page.tsx` (state: idle → running → done/error)
- Test: `frontend/test/composer.test.tsx`, `frontend/test/progress.test.tsx`

**Interfaces:**
- Consumes: `RunEvent`, `startRun`, `streamRun`.
- Produces: `<Composer onSubmit={(q:string)=>void} disabled={boolean} />`; `<ProgressList events:RunEvent[] />`.

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/test/progress.test.tsx
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import ProgressList from "@/components/ProgressList";

describe("ProgressList", () => {
  it("renders each step", () => {
    render(<ProgressList events={[
      { run_id: "r", step: "plan", status: "started" },
      { run_id: "r", step: "search", status: "progress", detail: 'Searching "rag"' },
    ]} />);
    expect(screen.getByText(/plan/i)).toBeInTheDocument();
    expect(screen.getByText(/Searching "rag"/)).toBeInTheDocument();
  });
});
```

```tsx
// frontend/test/composer.test.tsx
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import Composer from "@/components/Composer";

describe("Composer", () => {
  it("submits trimmed question", () => {
    const onSubmit = vi.fn();
    render(<Composer onSubmit={onSubmit} disabled={false} />);
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "  hi there  " } });
    fireEvent.click(screen.getByRole("button", { name: /research/i }));
    expect(onSubmit).toHaveBeenCalledWith("hi there");
  });
  it("disabled while running", () => {
    render(<Composer onSubmit={() => {}} disabled />);
    expect(screen.getByRole("textbox")).toBeDisabled();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- --run`
Expected: FAIL (components not found).

- [ ] **Step 3: Implement components + wire `page.tsx`**

`Composer`: controlled textarea + "Research" button; ignores blank; disabled when `disabled`. `ProgressList`: label per step (`plan→Planning`, `search→Searching`, `read→Reading sources`, `write→Writing`, `done→Done`, `error→Error`) + `detail`. `page.tsx`: on submit `startRun("research", q)` then `streamRun` appending events; render `<ProgressList>`; placeholder report block (Task 16 fills it); abort button closes the `EventSource`; error state with retry.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm test -- --run`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/components frontend/app/page.tsx frontend/test
git commit -m "feat(research): composer and live progress UI"
```

---

### Task 16: Report view + sources + history UI

**Files:**
- Create: `frontend/components/ReportView.tsx`, `frontend/components/SourceList.tsx`, `frontend/components/HistorySidebar.tsx`
- Modify: `frontend/app/page.tsx`
- Test: `frontend/test/report.test.tsx`, `frontend/test/history.test.tsx`

**Interfaces:**
- Consumes: `CapabilityResult`, `Citation`, `listRuns`, `getResult`.
- Produces: `<ReportView result:CapabilityResult />`; `<SourceList citations:Citation[] />`; `<HistorySidebar runs:RunSummary[] onSelect={(id:string)=>void} />`.

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/test/report.test.tsx
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import ReportView from "@/components/ReportView";

describe("ReportView", () => {
  it("renders markdown and clickable sources", () => {
    render(<ReportView result={{
      run_id: "r", capability_id: "research", status: "finished", report_markdown: "Finding [1].",
      citations: [{ index: 1, title: "Src", url: "https://example.com" }],
      sources: [], tokens: 0, cost: 0, duration_ms: 0,
    }} />);
    expect(screen.getByRole("link", { name: /Src/i })).toHaveAttribute("href", "https://example.com");
    expect(screen.getByText(/Finding/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- --run`
Expected: FAIL (components not found).

- [ ] **Step 3: Implement components + wire `page.tsx`**

`ReportView`: render `report_markdown` via react-markdown + remark-gfm; convert inline `[n]` to anchors to the matching citation URL; render `<SourceList>`. `SourceList`: ordered anchors opening in a new tab. `HistorySidebar`: list runs; click → `onSelect`. `page.tsx`: load `listRuns()` on mount; selecting a past run `getResult(id)` → `ReportView`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm test -- --run`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/components frontend/app/page.tsx frontend/test
git commit -m "feat(research): report, sources, and history UI"
```

---

### Task 17: Docker, env template, README, CI

**Files:**
- Create: `backend/Dockerfile`, `frontend/Dockerfile`, `docker-compose.yml`, `.env.example`, `.github/workflows/ci.yml`
- Create: `backend/.dockerignore`, `frontend/.dockerignore`
- Modify: `README.md`

**Interfaces:**
- Consumes: backend + frontend apps.
- Produces: runnable containers, env template, CI.

- [ ] **Step 1: Write the failing check**

Run: `docker compose config`
Expected: FAIL (`no configuration file provided: docker-compose.yml not found`).

- [ ] **Step 2: Implement**

`backend/Dockerfile`: `python:3.11-slim`, install from pyproject, copy `app/`, run uvicorn on 8000. `frontend/Dockerfile`: `node:20-alpine`, install, `npm run build`, `next start`. `docker-compose.yml`: `backend` (8000, mount `./data`, env from `.env`) + `frontend` (3000, `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000`); comment on pointing at local LM Studio/Ollama. `.env.example`: every spec §9 key with placeholders. `.dockerignore` each: `.env`, `data/`, `node_modules/`, `.next/`. `.github/workflows/ci.yml`: backend job (pip install + pytest) and frontend job (npm ci + test + build). README: overview, prereqs, local dev, env, Docker, tests, local↔cloud switch.

- [ ] **Step 3: Verify**

Run: `docker compose config` (valid), `cd backend && python -m pytest -q` (pass), `cd frontend && npm test -- --run && npm run build` (pass).

- [ ] **Step 4: Commit**

```bash
git add backend/Dockerfile backend/.dockerignore frontend/Dockerfile frontend/.dockerignore docker-compose.yml .env.example .github README.md
git commit -m "chore: docker, env template, CI, and docs"
```

---

## Later phases — module outlines

Each outline fixes components, interfaces, and acceptance criteria. **When a phase starts, write its detailed plan (same task format as above) from this outline**, then implement.

### Phase 2 — `verification`, `memory-notes`

**`verification`** — depends on `research`.
- Components: `verify(result:CapabilityResult)->VerificationReport`; run-engine post-step hook; `verified` flag on runs.
- Tasks: (1) `VerificationReport` contract; (2) verifier agent/prompt that checks each claim against cited sources; (3) engine hook + UI badge; (4) tests for unsupported-claim flagging and fail-open on verifier error.

**`memory-notes`** — depends on `core-platform`.
- Components: `MemoryStore` (SQLite + FTS5); tools `remember`, `recall`, `save_note`; context injection into every capability run.
- Tasks: (1) memory table + store; (2) the three tools; (3) inject recalled memory into the crew context; (4) UI to view/edit memories; (5) tests for cross-session recall and per-user scoping (stubbed until auth).

### Phase 3 — `doc-rag` — depends on `core-platform` (+ optional `memory-notes`)

- Components: ingestion pipeline (PDF/TXT/OCR), `get_embeddings`, vector store (FAISS or Chroma — open question), tool `query_documents(question,k)`, upload UI.
- Acceptance: answers cite specific chunks from specific documents; re-ingesting unchanged files is a no-op; ingestion is idempotent.
- Tasks: (1) embeddings factory impl; (2) ingestion + chunking; (3) vector store adapter; (4) `query_documents` tool; (5) upload + citations UI; (6) tests with a fixture PDF.

### Phase 4 — `auth-multiuser` → `email`, `calendar`, `tasks-reminders`

**`auth-multiuser`** — depends on `core-platform`.
- Components: users table, sessions, per-user scoping on runs/memory/documents, `auth_enabled` gate (already in `Settings`).
- Acceptance: user A can never read user B's runs/memories/documents; OAuth tokens stored encrypted.

**`email`** / **`calendar`** — depend on `auth-multiuser`.
- Components: `EmailProvider` / `CalendarProvider` protocols (Gmail/Outlook adapters); tools for draft/summarize/send and list/find/create; confirmation gate on send/create.
- Acceptance: least-privilege scopes; timezone-correct scheduling; sends require explicit confirmation.

**`tasks-reminders`** — depends on `core-platform` (+ `memory-notes`).
- Components: `TaskStore`; tools `add_task/list_tasks/complete_task/schedule_reminder`; scheduler loop.
- Acceptance: reminders fire at the due time; tasks survive restart.

### Phase 5 — `local-files`, `coding-help`

**`local-files`** — depends on `core-platform`.
- Components: tools `list_files/read_file/write_file/move_file`, sandboxed to a configured root.
- Acceptance: operations outside the root are refused; destructive ops require confirmation.

**`coding-help`** — depends on `core-platform`.
- Components: tool `run_python(code)` in a sandbox (time/memory/output limits); context tools.
- Acceptance: sandbox has no host filesystem/network access; runs are bounded.

### Phase 6 — `observability`, `deployment-ops`

**`observability`** — depends on `core-platform`.
- Components: structured logs with `run_id`; per-run tokens/cost/duration (already recorded); a tracing hook (MLflow/LangSmith); metrics view.
- Acceptance: every run's tokens/cost/duration visible; trace export optional.

**`deployment-ops`** — depends on `core-platform`.
- Components: Postgres/Redis compose profile; migrations; CI/CD to the chosen host; backups; env docs.
- Acceptance: `docker compose up` serves a working app from a clean checkout; CI green; backup/restore documented.

---

## Cross-phase concerns

- **Security (every phase):** SSRF and prompt-injection guards are re-tested whenever a new external input source is added (documents, email, calendar). Never relax them to make a demo work.
- **Provider factory hygiene:** new provider kinds (embeddings, email, calendar) get a factory + `ConfigError`s + offline fakes, following `llm.py`.
- **Extensibility check:** after each phase, re-run the dummy-capability test (Task 7) to confirm the core stayed capability-agnostic.
- **Docs:** the master spec is updated (not duplicated) when a decision changes; each module's spec traces to its module id.

## Self-Review

**1. Spec coverage:** spec §6 core → Tasks 1–9; `research` (§8 M2) → Tasks 10–17; capability map (§3) → phase outlines; security (§14, Review Focus) → Tasks 4/11/12/13; deployment (§13) → Task 17; later modules (§8 M3–M13) → phase outlines. Open questions (§18) stay open in the spec.

**2. Step scan:** each step is one checkable action; bodies are left to the implementer except algorithm-bearing `is_safe_url`, `SearchChain.search`, and `collect_citations`, which are specified precisely.

**3. Type consistency:** `CapabilityResult` (not the old `ResearchResult`) is used across Tasks 3, 5, 7, 13, 14, 16; `RunEvent` step/status literals consistent across 3, 7, 13; registry names (`ToolRegistry.get/names`, `CapabilityRegistry.create/ids`) consistent across 6, 7, 8, 14.

**4. Review Focus coverage:** injection (12), SSRF (11), all-fetch-failure (13), token/time cap (13), empty input (3, 14), capability isolation (7).

**5. Proportion:** Phase 0–1 are task-detailed as needed to build; later phases are outlines by design, so the document stays a plan rather than a transcript of unbuilt code.
