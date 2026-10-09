# Spec: Atlas — AI Personal Assistant Platform Master Spec

- **Date:** 2026-10-09
- **Status:** Draft for review
- **Owner:** Santosh Singh
- **Supersedes:** `docs/superpowers/specs/2026-10-09-research-assistant-design.md`
- **Related:** `docs/superpowers/plans/2026-10-09-atlas-master-plan.md`

---

## 0. Assumptions I'm making

Read these first. If any is wrong, correct it before we build on it.

1. **Solo builder.** You (Santosh) build and maintain this yourself; multi-user is a later phase, not a day-one requirement.
2. **Web application.** Next.js front end + Python (FastAPI) backend. Not native mobile.
3. **Agent framework is CrewAI**, with LangChain-compatible chat models, because that matches your existing experience.
4. **Start local, deploy to cloud.** Development uses a local LM Studio/Ollama model; production uses a cloud provider. The switch is configuration only.
5. **Deployment target is undecided**, so the design is container-based and host-agnostic.
6. **v1 is the Research Assistant.** Every other capability is added later as a pluggable tool behind a stable interface, not by rewriting the core.
7. **English-only, single-region** for now. No i18n, no multi-region.
8. **Budget-conscious.** Prefer free tiers (Tavily free tier, DuckDuckGo, SQLite, free hosting) until a cloud budget exists.
9. **This master spec is the source of truth.** Each later module gets its own focused spec that traces to a module id in the capability map below.

> If these assumptions are right, the rest of this spec is the plan of record. If not, fix them here first — they are cheap to change now and expensive to change after code exists.

---

## 1. Objective

Build a **personal AI assistant platform**: one web app where you talk to an assistant that can research, answer questions about your documents, remember things, and (later) help with email, calendar, tasks, coding, and local files.

The value is not any single capability — it is the **platform**: a stable core where each new capability plugs in as a tool, so the assistant grows without rewrites. The Research Assistant is the first vertical slice because it is self-contained, needs no OAuth, and exercises the entire architecture (agent loop → tools → streaming → persistence → UI → deploy).

**Who it's for:** you, as a daily-use assistant and a portfolio-grade demonstration of end-to-end ML/AI engineering.

**What success looks like:** ask a real research question in the web UI and get back, within a few minutes, a readable report whose claims trace to working citations — and afterward add a second capability (e.g. document Q&A) by writing a tool, without touching the agent core.

---

## 2. Product principles

1. **Vertical slices, not sprawl.** Ship one capability end-to-end before starting the next.
2. **Pluggable capabilities.** Every capability is a module exposing tools through a registry. The core never imports a capability directly.
3. **Provider-agnostic.** LLM, search, and embeddings sit behind factories selected by config. No provider names leak into business logic.
4. **Reliability over autonomy.** Structured, observable agent flows beat free-form loops. Grounded output (citations) beats fluent output.
5. **Secure by default.** Untrusted input (web pages, documents, emails) is data, never instructions. Secrets never touch logs or the repo.
6. **Testable seams.** Every external dependency (LLM, search, network, clock) is injectable so tests run with no network and no keys.
7. **Deploy-agnostic.** One config change moves local → cloud; one container change moves host.

---

## 3. Capability map  ⚠️ THE GATE

This is the decomposition. **Review module boundaries, dependency direction, and build order before any module is built.** Module ids are stable and never renamed; specs, plans, and code select work by these ids.

| Module id | Responsibility | Depends on |
|---|---|---|
| `core-platform` | Assistant core: config, contracts, run engine, event bus, tool registry, provider factories, persistence, API shell, frontend shell | — |
| `research` | **v1 anchor.** Web research → cited report | `core-platform` |
| `verification` | Claim/citation verification pass over any capability's output | `research` |
| `memory-notes` | Long-term memory + notes: remember facts, preferences, past runs | `core-platform` |
| `doc-rag` | Chat over your own documents (ingestion, embeddings, retrieval) | `core-platform`, `memory-notes` (optional) |
| `local-files` | Read/write/organize files on the local machine | `core-platform` |
| `tasks-reminders` | To-dos, reminders, scheduled jobs | `core-platform`, `memory-notes` (optional) |
| `auth-multiuser` | Accounts, sessions, per-user data isolation | `core-platform` |
| `email` | Draft/summarize/reply to email | `core-platform`, `auth-multiuser` |
| `calendar` | Events, scheduling, availability | `core-platform`, `auth-multiuser` |
| `coding-help` | Write/explain/debug code, sandboxed execution | `core-platform` |
| `observability` | Tracing, cost/token dashboards, alerting | `core-platform` |
| `deployment-ops` | Containers, environments, CI/CD, backups | `core-platform` |

**Dependency direction (no cycles):**

```
auth-multiuser ─┐
memory-notes ───┤
local-files ────┤
coding-help ────┼──▷ core-platform
tasks-reminders ┘        ▲
doc-rag ────────────────┤
                         │
              email ◁─────┘ (also ◁ auth-multiuser)
              calendar ◁──┘ (also ◁ auth-multiuser)
              verification ◁ research
              observability ◁ core-platform
              deployment-ops ◁ core-platform
```

**Build order:**

```
Phase 0  core-platform        (foundation)
Phase 1  research             (v1 anchor — this is what we ship first)
Phase 2  verification, memory-notes
Phase 3  doc-rag
Phase 4  auth-multiuser → email, calendar, tasks-reminders
Phase 5  local-files, coding-help
Phase 6  observability + deployment-ops hardening
```

**Rule:** if two modules would each need the other, they are one module. Split only when a module can ship and be verified on its own.

---

## 4. Users and use cases

- **Primary user:** the owner (you). Uses it daily from a browser, on your own data.
- **Secondary user:** portfolio reviewers (recruiters, engineers) who read the code and try the deployed app.

| Capability | Representative use case |
|---|---|
| research | "Summarize the current state of small-model fine-tuning, with sources." |
| doc-rag | "What does my lease say about early termination?" |
| memory-notes | "Remember I prefer concise answers." / "What did I conclude about vector DBs?" |
| tasks-reminders | "Remind me to review PRs every weekday at 9." |
| email | "Draft a polite follow-up to this thread." |
| calendar | "Find 30 minutes with these constraints next week." |
| coding-help | "Explain this traceback and propose a fix." |
| local-files | "Organize my Downloads folder by type." |

---

## 5. System architecture

### 5.1 Layers

```
┌────────────────────────────────────────────────────────────┐
│ Frontend (Next.js / React / TS / Tailwind)                  │
│  chat UI · streaming view · history · per-capability panels │
└───────────────▲───────────────────────────┬────────────────┘
                │ SSE / REST                 │
┌───────────────┴───────────────────────────▼────────────────┐
│ API (FastAPI)                                               │
│  routers · auth · validation · SSE streaming · rate limits │
└───────────────▲───────────────────────────┬────────────────┘
                │                            │
┌───────────────┴────────────────────────────▼────────────────┐
│ Assistant Core                                              │
│  orchestrator · run engine · event bus · tool registry ·    │
│  capability registry · memory interface                     │
└───▲──────────────▲───────────────▲──────────────▲───────────┘
    │              │               │              │
┌───┴────┐   ┌─────┴─────┐   ┌─────┴─────┐  ┌─────┴──────┐
│research│   │  doc-rag  │   │memory-notes│ │ ...modules │
│ (crew) │   │ (retriever)│  │ (store)    │ │ (all as    │
│        │   │           │   │            │ │  tools)    │
└───┬────┘   └─────┬─────┘   └─────┬──────┘ └─────┬──────┘
    │              │               │              │
┌───▼──────────────▼───────────────▼──────────────▼──────────┐
│ Providers & integrations (factories)                        │
│  LLM (local|openai|mistral) · Search (tavily→ddg) ·         │
│  Embeddings · Fetch · OAuth · Email/Calendar APIs           │
└───────────────▲───────────────────────────────▲─────────────┘
                │                                │
┌───────────────┴──────────────┐   ┌─────────────┴───────────┐
│ Persistence (SQLite→Postgres)│   │ Observability (logs,    │
│ runs · steps · citations ·   │   │ traces, cost metrics)   │
│ memory · documents · users   │   └─────────────────────────┘
└──────────────────────────────┘
```

### 5.2 Request lifecycle (generic)

1. UI sends a request (a question plus an optional capability/mode).
2. API validates and creates a **run**.
3. Orchestrator selects the capability (explicit mode in v1; router later).
4. Capability builds its agent flow using registered tools and the configured LLM.
5. The run engine emits **events**; the event bus fans them out to SSE and persistence.
6. On completion the result (+ citations/memory writes) is persisted.
7. UI renders the result; the run appears in history.

---

## 6. Core platform design (`core-platform`)

The core is the only part every capability depends on, so it stays small and capability-agnostic.

### 6.1 Components

- **Config** — `Settings` (pydantic-settings) read from environment. Single source for provider selection, limits, URLs, secrets.
- **Contracts** — pydantic models shared across API, capabilities, and store (`RunEvent`, `Citation`, `ResearchResult`, tool I/O types, `CapabilityResult`).
- **Tool registry** — capabilities register named, typed tools. Tools declare `name`, `description`, `input_schema`, `output_type`, and `run()`. The core never imports a capability to use its tools.
- **Capability registry** — maps a capability id (`research`, `doc-rag`, …) to a factory that produces its agent flow. The orchestrator uses ids, not imports.
- **Run engine** — creates a run, drives a capability's flow, enforces time/token caps, persists steps, and produces a result.
- **Event bus** — per-run pub/sub; a run's events stream to SSE consumers and are written to the store. Terminal events close the stream.
- **Provider factories** — `get_llm`, `get_search_chain`, `get_embeddings`, chosen by config; raise clear `ConfigError`s.
- **Persistence** — `RunStore` protocol with a SQLite implementation; designed so a Postgres implementation is a drop-in later.
- **API shell** — health, runs, capability dispatch, SSE. Auth is a no-op hook in v1, filled by `auth-multiuser` later.
- **Frontend shell** — layout, theme, typed API client, SSE client, capability panels.

### 6.2 Extensibility contract (the seam that matters)

To add a capability later, a developer (you) writes:

1. A module folder under `backend/app/capabilities/<id>/` with its tools and flow.
2. A `register(registry)` function exposing tools and a capability factory.
3. UI panel(s) registered by capability id.

No change to `core-platform` is required to add a capability whose needs are already covered by the tool interface. If a capability needs a new provider kind or a new persistence table, that is an explicit core change with its own spec — not a silent one.

---

## 7. Architecture decisions (ADRs, condensed)

| # | Decision | Rationale | Cost if wrong |
|---|---|---|---|
| ADR-1 | Agent framework: **CrewAI** | Matches experience; multi-agent narrative for portfolio | Framework churn; mitigated by keeping flows behind the capability interface |
| ADR-2 | **Sequential crews per capability**; a supervisor/router added later | Predictable, streamable, fewer failure modes than hierarchical | Later routing needs the orchestrator seam (already designed) |
| ADR-3 | **Tool registry + capability registry** | Core never imports capabilities; adding one is additive | Slight up-front indirection |
| ADR-4 | **Provider factories** for LLM/search/embeddings | Local↔cloud and Tavily↔DDG become config | An abstraction layer to maintain |
| ADR-5 | Persistence: **SQLite now, Postgres later** behind a protocol | Zero-ops start; real scale path | Migration work later (bounded by the protocol) |
| ADR-6 | Streaming: **SSE** (not WebSocket) | One-way server→client fits progress streams; simpler infra | No client→server streaming mid-run (not needed yet) |
| ADR-7 | Config: **env-only**, `.env` git-ignored, `.env.example` tracked | 12-factor; deploy-agnostic | None significant |
| ADR-8 | Security: **SSRF guard**, **prompt-injection guard**, **CORS allowlist**, **secrets never logged** | Untrusted web/doc/email input is the main risk | A bypass is a real vulnerability — hence dedicated tests |
| ADR-9 | File storage: local volume for v1; object store later | Simplicity | Migration later |
| ADR-10 | Observability: structured logs + run/cost metrics now; tracing (MLflow/LangSmith) hook later | Diagnose without a tracing vendor | Added later behind a hook |

---

## 8. Module specs

Each module: purpose, scope, interfaces, and acceptance criteria. Later modules are specified at design level here and get their own detailed spec + plan when their phase starts.

### M1 `core-platform` — Assistant core

- **Purpose:** capability-agnostic foundation described in section 6.
- **In scope:** config, contracts, tool/capability registries, run engine, event bus, provider factories (LLM now; search/embeddings factories defined now), SQLite store, API shell, frontend shell, Docker, tests.
- **Out of scope:** any specific capability's behavior.
- **Interfaces:** `Settings`, contracts module, `ToolRegistry.register()`, `CapabilityRegistry.register()`, `RunEngine.run()`, `EventBus.publish()/stream()`, `RunStore`, `get_llm()`, HTTP routes `POST /api/runs`, `GET /api/runs/{id}/stream`, `GET /api/runs/{id}`, `GET /api/runs`, `GET /healthz`.
- **Acceptance criteria:**
  - Health reports provider names, never secrets.
  - A run streams ordered events and persists them.
  - Adding a dummy capability requires no core edits (proven by a test capability).
  - `local`↔`openai`↔`mistral` and Tavily↔DDG are env-only changes.

### M2 `research` — Research assistant (v1 anchor)

- **Purpose:** turn a question into a structured, citation-backed report.
- **Scope in:** plan → search → read → write; sequential CrewAI crew (Planner → Researcher → Writer); pluggable search with fallback; page fetch with SSRF guard; SSE progress; report + sources UI; run history.
- **Scope out:** the Verifier (M3), scheduled/recurring research, PDF export.
- **Interfaces:** tools `web_search(query, k)`, `fetch_page(url)`; `ResearchOptions`, `ResearchResult`, `Citation`, `RunEvent`; `POST /api/research` (or `POST /api/runs` with `capability="research"`).
- **Acceptance criteria:**
  - A run returns within the configured timeout a Markdown report with inline `[n]` citations and a numbered sources list.
  - Every citation URL was actually fetched or returned by search; no invented sources.
  - A search-provider failure falls back silently; all-fetch failure yields a "no sources found" report.
  - Token/time cap hit ends cleanly with a labelled partial result.
  - Empty/too-short question is rejected with 422.

### M3 `verification` — Output verifier

- **Purpose:** check any capability's output for uncited or unsupported claims before it is shown; flag or drop them.
- **Depends on:** `research` (first consumer).
- **Interfaces:** `verify(result: CapabilityResult) -> VerificationReport`, registered as an optional post-processing step in the run engine.
- **Acceptance criteria:** unsupported claims are flagged; a run can be marked `verified`/`unverified`; verifier failure never blocks a result (fails open with a flag).
- **Status:** deferred from v1 (spec §14 of the prior design); first enhancement after v1.

### M4 `memory-notes` — Long-term memory + notes

- **Purpose:** remember facts, preferences, and past runs; store and recall notes.
- **Interfaces:** `MemoryStore` (SQLite table + FTS or embeddings); tools `remember(text, tags)`, `recall(query, k)`, `save_note(text)`; injected into every capability's context.
- **Acceptance criteria:** something remembered in one session is recallable in a later one; memory is scoped per user once `auth-multiuser` lands.

### M5 `doc-rag` — Document Q&A

- **Purpose:** ingest your documents and answer questions with citations.
- **Interfaces:** ingestion pipeline (PDF/TXT/OCR), embeddings via `get_embeddings()`, vector store (FAISS/Chroma), tool `query_documents(question, k)`.
- **Acceptance criteria:** answers cite specific chunks from specific documents; ingestion is idempotent; re-ingesting unchanged files is a no-op.

### M6 `local-files` — Local file access

- **Purpose:** read/write/organize files on the machine.
- **Interfaces:** tools `list_files`, `read_file`, `write_file`, `move_file`, all sandboxed to a configured root.
- **Acceptance criteria:** operations outside the configured root are refused; destructive ops require confirmation.

### M7 `tasks-reminders` — Tasks + reminders

- **Purpose:** create/track tasks and fire reminders.
- **Interfaces:** `TaskStore`; tools `add_task`, `list_tasks`, `complete_task`, `schedule_reminder`; a scheduler loop.
- **Acceptance criteria:** a reminder with a due time surfaces at the right time; tasks survive restart.

### M8 `auth-multiuser` — Accounts + isolation

- **Purpose:** let more than one person use the app without seeing each other's data.
- **Interfaces:** sign-up/login, sessions, per-user scoping on every store and run.
- **Acceptance criteria:** user A can never read user B's runs, memories, or documents; OAuth tokens (M9/M10) are stored encrypted.

### M9 `email` — Email assistance

- **Purpose:** draft, summarize, and reply to email.
- **Depends on:** `auth-multiuser` (OAuth).
- **Interfaces:** provider adapters (Gmail/Outlook) behind an `EmailProvider` protocol; tools `draft_email`, `summarize_thread`, `send_email` (send behind explicit confirmation).
- **Acceptance criteria:** reading and drafting work with least-privilege scopes; sending always requires explicit user confirmation.

### M10 `calendar` — Calendar + scheduling

- **Purpose:** read events and find scheduling slots.
- **Depends on:** `auth-multiuser`.
- **Interfaces:** `CalendarProvider` protocol; tools `list_events`, `find_slot`, `create_event` (behind confirmation).
- **Acceptance criteria:** timezone handling is correct; created events round-trip.

### M11 `coding-help` — Coding assistant

- **Purpose:** write/explain/debug code; optionally run it sandboxed.
- **Interfaces:** tool `run_python(code)` executed in a sandbox with time/memory/output limits; context tools for file reading.
- **Acceptance criteria:** execution is sandboxed and bounded; no host filesystem/network access from the sandbox.

### M12 `observability` — Tracing + cost

- **Purpose:** see what the assistant did and what it cost.
- **Interfaces:** structured logs with `run_id`; per-run tokens/cost; tracing hook (MLflow/LangSmith) wired later; a small metrics view.
- **Acceptance criteria:** every run's tokens/cost/duration are recorded and visible.

### M13 `deployment-ops` — Ship + operate

- **Purpose:** run it anywhere, reproducibly.
- **Interfaces:** backend/frontend Dockerfiles, `docker-compose.yml`, `.env.example`, CI (test on push), Postgres/Redis profile, backups.
- **Acceptance criteria:** `docker compose up` serves a working app from a clean checkout; CI runs backend + frontend tests.

---

## 9. Tech stack

| Layer | Choice | Version floor |
|---|---|---|
| Language (backend) | Python | 3.11 |
| API | FastAPI + Uvicorn | fastapi ≥0.110 |
| Agents | CrewAI | ≥0.60 |
| LLM clients | langchain-openai, langchain-mistralai | ≥0.1 |
| Models/validation | pydantic v2, pydantic-settings | pydantic ≥2.6 |
| ORM | SQLModel (SQLAlchemy) | ≥0.0.16 |
| HTTP | httpx, requests | httpx ≥0.27 |
| Extraction | trafilatura, BeautifulSoup4 | trafilatura ≥1.8 |
| Search | tavily-python, ddgs | — |
| Backend tests | pytest, pytest-asyncio, respx | pytest ≥8 |
| Frontend | Next.js (App Router), React, TypeScript | Next 14, React 18, TS 5 |
| Styling | Tailwind CSS | 3 |
| Markdown | react-markdown, remark-gfm | — |
| Frontend tests | Vitest, Testing Library, jsdom | — |
| Lint/format | ruff (backend), eslint/prettier (frontend) | ruff ≥0.4 |

---

## 10. Commands

```bash
# Backend
cd backend
pip install -e ".[dev]"          # install
python -m pytest -q              # test
ruff check app tests             # lint
uvicorn app.main:app --reload    # dev server (http://localhost:8000)

# Frontend
cd frontend
npm install                      # install
npm test -- --run                # test
npm run lint                     # lint
npm run dev                      # dev server (http://localhost:3000)
npm run build                    # production build

# Whole stack
docker compose up --build        # run backend + frontend
docker compose config            # validate compose
```

---

## 11. Project structure

```
Atlas/
  backend/
    app/
      config/          # Settings
      schemas.py       # shared contracts (or app/contracts/)
      core/
        registry.py    # tool + capability registries
        engine.py      # run engine
        events.py      # event bus
      providers/
        llm.py         # get_llm
        search/        # base, tavily, duckduckgo, chain
        embeddings.py  # get_embeddings (stub in v1)
      store/           # models + repository (SQLite)
      capabilities/
        research/      # agents, runner, tools (v1)
      api/             # routers, sse, broker
      main.py
    tests/
    pyproject.toml
    Dockerfile
  frontend/
    app/               # Next.js App Router
    components/        # Composer, ProgressList, ReportView, SourceList, HistorySidebar
    lib/               # api client, types, sse client
    test/
    Dockerfile
  docker-compose.yml
  .env.example
  README.md
  docs/superpowers/specs/    # this spec + module specs
  docs/superpowers/plans/    # master plan + module plans
```

---

## 12. Code style

One real snippet beats paragraphs. Backend style:

```python
# backend/app/providers/search/chain.py
from __future__ import annotations

from app.providers.search.base import SearchProvider, SearchError
from app.schemas import SearchResult


class SearchChain:
    """Try providers in order; return the first non-empty result set."""

    def __init__(self, providers: list[SearchProvider]) -> None:
        self._providers = providers

    @property
    def names(self) -> list[str]:
        return [p.name for p in self._providers]

    def search(self, query: str, k: int) -> list[SearchResult]:
        last_error: Exception | None = None
        for provider in self._providers:
            try:
                results = provider.search(query, k)
            except Exception as exc:  # provider failure must never kill the run
                last_error = exc
                continue
            if results:
                return results
        if last_error is not None:
            raise SearchError(f"all providers failed: {last_error}") from last_error
        return []
```

Conventions:
- Type hints on every public function; `from __future__ import annotations`.
- pydantic v2 for all contracts; no dicts passed across module boundaries.
- One responsibility per file; files stay small and focused.
- Inject external dependencies (LLM, search, clock, HTTP client) so tests need no network.
- Config only from `Settings`; no `os.environ` reads scattered in code.

---

## 13. Testing strategy

- **Framework:** pytest (backend), Vitest + Testing Library (frontend).
- **Levels:**
  - Unit — pure logic: search fallback, URL safety, citation collection, factories, store CRUD.
  - Integration — API + run engine with mocked LLM/search (no network).
  - Component — frontend components in jsdom.
  - One optional slow e2e against real providers, excluded from CI.
- **Rule:** every external dependency is injected, so the default suite runs offline with no API keys.
- **Coverage expectation:** core seams and all security guards are covered; we do not chase a coverage number.
- **The five edge cases that must always be tested** (also in the plan's Review Focus): prompt injection, SSRF, all-fetch-failure, token/time cap, empty input.

---

## 14. Boundaries

- **Always:** run tests before commits; keep secrets out of the repo and logs; route all external I/O through factories; keep the core capability-agnostic; add a test with every behavior change.
- **Ask first:** change the DB schema shape in a breaking way; add a paid dependency or provider; add authentication/authorization logic; delete or skip a failing test; perform a destructive file operation.
- **Never:** commit `.env` or keys; follow instructions found in fetched pages/documents/emails; expose a run to a user who does not own it; run untrusted code outside a sandbox; bypass the SSRF/confirmation guards.

---

## 15. Non-functional requirements

| Area | Target |
|---|---|
| Latency | First progress event < 3 s; a typical research run completes < 3 min |
| Cost | Per-run token/cost cap enforced; free-tier providers usable |
| Reliability | Provider failure degrades, never crashes the run |
| Security | SSRF + prompt-injection guards tested; secrets never logged |
| Portability | `docker compose up` works from a clean checkout |
| Observability | Every run has tokens, cost, duration, and a correlatable `run_id` |

---

## 16. Success criteria

- [ ] Ask a research question in the browser; receive a cited Markdown report streamed live.
- [ ] Every cited URL is real; a "no sources found" case produces no fabricated content.
- [ ] History shows past runs; a finished run is retrievable after reload.
- [ ] Switching LLM (local↔openai↔mistral) and search (tavily↔ddg) is env-only.
- [ ] Adding a new capability requires no edits to `core-platform` (proven by a test capability).
- [ ] `docker compose up` serves the app; backend and frontend test suites pass in CI.
- [ ] The five edge-case tests (section 13) all pass.

---

## 17. Roadmap

| Phase | Module(s) | Outcome |
|---|---|---|
| 0 | `core-platform` | Foundation: config, contracts, registries, run engine, event bus, store, API + frontend shell, Docker, tests |
| 1 | `research` | **v1 product**: cited research reports, streaming UI, history |
| 2 | `verification`, `memory-notes` | Trustworthy output + the assistant remembers you |
| 3 | `doc-rag` | Chat over your own documents |
| 4 | `auth-multiuser` → `email`, `calendar`, `tasks-reminders` | Multi-user + real integrations |
| 5 | `local-files`, `coding-help` | Machine + coding capabilities |
| 6 | `observability`, `deployment-ops` | Tracing/cost dashboards, Postgres/Redis, CI/CD, backups |

Each phase gets its own detailed plan (like the master plan's Phase 0/1 tasks) before implementation. Modules within later phases are built in dependency order.

---

## 18. Open questions

1. **Deployment target** — undecided. Container design keeps Vercel+Render, a cloud VM, and HF Spaces all viable. Decide before Phase 6.
2. **Vector store** — FAISS vs Chroma for `doc-rag`. Decide before Phase 3.
3. **Memory representation** — FTS keyword vs embeddings. Depends on `doc-rag` decisions; decide before Phase 2.
4. **Auth model** — self-hosted sessions vs OAuth-only. Decide before Phase 4.
5. **Local model** — LM Studio vs Ollama as the default dev model. Decide before Phase 1.
