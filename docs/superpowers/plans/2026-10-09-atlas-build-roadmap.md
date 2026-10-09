# Atlas — Phase-Wise Build Roadmap (Builder's Guide)

**Goal:** Build Atlas phase by phase as the human implementer, with AI acting as reviewer/helper at defined checkpoints, ending with a deployed, capability-extensible assistant platform.

**Architecture:** Capability-agnostic `core-platform` (config, contracts, registries, run engine, event bus, provider factories, SQLite store, FastAPI + SSE, Next.js shell) with each capability plugging in as a registered module. v1 = `research` (sequential CrewAI crew: Planner → Researcher → Writer).

**Tech Stack:** Python 3.11, FastAPI, CrewAI, LangChain (openai/mistral), pydantic v2, SQLModel/SQLite, httpx, trafilatura, BeautifulSoup, pytest; Next.js 14, TypeScript, Tailwind, Vitest.

**Spec (binding authority):** `docs/superpowers/specs/2026-10-09-atlas-master-spec.md`
**Detailed tasks (Phases 0–1):** `docs/superpowers/plans/2026-10-09-atlas-master-plan.md` (Tasks 1–17, each with exact failing test → implement → pass → commit)

> This roadmap does **not** repeat the master plan's tasks — it tells you **what order to do them in, what "done" means, and when to bring work to review**. The master plan is your instruction sheet; this document is your map and quality gate.

---

## 0. How this works (you build, AI reviews)

**The loop, per task:**

1. Read the task in the master plan (e.g., "Task 5: Run store").
2. Follow its steps exactly — **write the failing test first (RED), then implement (GREEN)**.
3. Run the full suite + lint: `cd backend && python -m pytest -q && ruff check app tests`.
4. Commit using the task's commit message.
5. At the task's **checkpoint** (marked below) or whenever you're stuck → bring the work to AI review.

**How to request a review (checkpoint protocol):**

Tell AI: *"Review Task N"* and provide:

- The commit range (e.g., `git diff <base>..HEAD --stat` plus the full diff, or just say "review my last commit")
- Test output (`pytest -q` tail)
- Anything that felt wrong or uncertain

AI reviews against the **spec + master plan task text** and returns: spec compliance ✅/❌, findings by severity (Critical / Important / Minor), and fixes to consider. **Fix Critical/Important before moving on.** Minor findings get logged (below) and triaged at the phase gate.

**Rule of thumb:** never start Task N+1 with an open Critical/Important finding from Task N.

**When you're stuck (any time):** paste the error + what you expected + what you tried. AI debugs with you — don't sit on a broken build.

---

## 1. Global Constraints (every task, every phase)

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

## 2. Review Focus (the six failure modes that must always be tested)

1. Fetched page text contains adversarial instructions — treated as data, never executed (Task 12).
2. `fetch_page` targets a private/loopback/link-local host or non-http scheme — refused (Task 11).
3. Search returns results but every fetch fails — "no sources found" report, never fabricated content (Task 13).
4. Run exceeds token cap or timeout mid-flight — stops cleanly with a labelled partial result (Task 13).
5. Empty/too-short question — rejected with 422, not a broken run (Tasks 3, 14).
6. A new capability can be added with no `core-platform` edits, and a run still streams + persists (Task 7).

---

## 3. Phase overview

| Phase | Name | Source of tasks | You build | Gate review with AI |
|---|---|---|---|---|
| 0 | `core-platform` foundation | Master plan **Tasks 1–9** (detailed) | Config → contracts → store → registries → engine → API → frontend shell | After Task 9 |
| 1 | `research` (v1) | Master plan **Tasks 10–17** (detailed) | Search → SSRF fetch → crew → runner → wiring → UI → Docker/CI | After Task 17 — **v1 ships** |
| 2 | `verification` + `memory-notes` | *Ask AI to write detailed plan first* | Verifier pass + long-term memory | End of phase |
| 3 | `doc-rag` | *Ask AI to write detailed plan first* | Document ingestion + retrieval Q&A | End of phase |
| 4 | `auth-multiuser` → `email`, `calendar`, `tasks-reminders` | *Ask AI to write detailed plan first* | Accounts + integrations | End of phase (per module) |
| 5 | `local-files`, `coding-help` | *Ask AI to write detailed plan first* | Sandboxed file + code capabilities | End of phase (per module) |
| 6 | `observability`, `deployment-ops` | *Ask AI to write detailed plan first* | Dashboards, Postgres/Redis, CI/CD, backups | End of phase → **launch** |

**Rule:** one phase at a time, in order. Never start phase N+1 until phase N's gate review is clean (or its findings are explicitly accepted/deferred).

---

## 4. Phase 0 — `core-platform` (Tasks 1–9)

**Branch:** `phase-0-core` (merge to `main` after gate review)
**Suggested pace:** 1 task/session to start; you'll speed up.

- [ ] **Task 1** — Backend scaffold + tooling → *no checkpoint, proceed*
- [ ] **Task 2** — Settings (config) → *no checkpoint, proceed*
- [ ] **Task 3** — Domain contracts → ⚡ **mini-review #1** (schemas are the project's vocabulary; a mistake here multiplies). Bring: diff + pytest output.
- [ ] **Task 4** — Provider factories (LLM + embeddings stub)
- [ ] **Task 5** — Run store (SQLite) → ⚡ **mini-review #2** (persistence shape is hard to change later; spec §14 says schema-breaking changes need approval). Bring: diff + test output.
- [ ] **Task 6** — Tool + capability registries
- [ ] **Task 7** — Event bus + run engine → ⚡ **mandatory review #3** — this proves Review Focus #6 (extensibility seam). Do not proceed without a clean review. Bring: diff + test output.
- [ ] **Task 8** — API shell + SSE
- [ ] **Task 9** — Frontend scaffold + typed API/SSE client

### 🚪 Phase 0 gate review

Bring to AI:

1. `git log --oneline main..phase-0-core` + full diff (or the branch itself)
2. Full test output for backend and frontend
3. Confirmation: `ruff check app tests` clean, `npm run lint` clean

AI verifies: spec §6 (M1 acceptance criteria), Global Constraints, Review Focus #6, and triages any deferred minor findings.
**Only after gate = clean: merge `phase-0-core` → `main`, start Phase 1.**

---

## 5. Phase 1 — `research` v1 (Tasks 10–17)

**Branch:** `phase-1-research`

- [ ] **Task 10** — Search providers + fallback chain
- [ ] **Task 11** — Page fetcher with SSRF guard → ⚡ **mandatory security review #4** (Review Focus #2 — never skip this one). Bring: diff + full `test_fetch_page.py` output.
- [ ] **Task 12** — Research crew (Planner → Researcher → Writer) → ⚡ **mandatory review #5** (prompt-injection guard lives in the prompts — Review Focus #1). Bring: diff + prompts.py content.
- [ ] **Task 13** — Research runner (events, caps, citations) → ⚡ **mandatory review #6** (covers Review Focus #3 and #4: no-sources + token/time cap).
- [ ] **Task 14** — Capability registration + API wiring → ⚡ **mini-review #7** (integration seam: "core never imports a capability" must hold). Includes Review Focus #5 (422 on short question).
- [ ] **Task 15** — Composer + live progress UI
- [ ] **Task 16** — Report view + sources + history UI
- [ ] **Task 17** — Docker, env template, README, CI

### 🚪 Phase 1 gate review (= v1 release)

1. Full diffs of Tasks 10–17 + all test output.
2. **Manual smoke test, in this order:**
   - [ ] `docker compose config` validates; `docker compose up --build` serves both apps
   - [ ] Ask a real research question in the browser → streamed progress → cited Markdown report
   - [ ] Every cited URL opens and matches its claim (spot-check all of them)
   - [ ] Ask a nonsense/niche question → check for "No sources found" rather than fabrication
   - [ ] Send an empty/1-char question → 422, UI shows an error not a crash
   - [ ] Reload page → history shows the run; clicking it re-opens the report
   - [ ] Switch `SEARCH_PROVIDERS=duckduckgo` (or LLM provider) in `.env` → restart → works, no code change
3. AI runs the **full spec §16 success-criteria checklist** as the release review.

**Only after gate = clean: merge → `main`, tag `v1.0.0`.** 🎉

---

## 6. Phase 2 — `verification` + `memory-notes`

**Pre-phase action (do this first):** tell AI — *"Write a detailed plan for Phase 2 from the master plan's Phase 2 outline and spec M3/M4"* → it produces a task-by-task plan in the same format as the master plan, saved to `docs/superpowers/plans/`.
**Open question #3 due now:** memory representation — FTS keyword vs embeddings. The master plan's outline assumes SQLite + FTS5 (cheap, offline); confirm or revisit with AI before building.

- **`verification`:** `VerificationReport` contract → verifier prompt (checks claims against cited sources) → engine post-step hook + `verified`/`unverified` UI badge → tests for flagging + fail-open behavior.
- **`memory-notes`:** memory table + store (SQLite FTS5) → `remember` / `recall` / `save_note` tools → inject recalled memory into crew context → memory UI → tests for cross-session recall.

**Acceptance highlights (from spec):** unsupported claims flagged; verifier failure never blocks a result; something remembered in one session is recallable in a later one.

### 🚪 Phase 2 gate review
Diffs + tests + demo ("remember X" → restart → "what did I say about X"), AI verifies spec M3/M4 acceptance criteria.

---

## 7. Phase 3 — `doc-rag`

**Pre-phase action:** ask AI for the detailed Phase 3 plan (outline in master plan). **Decide first (open question #2):** FAISS vs Chroma — AI can lay out trade-offs.

- Embeddings factory implementation (replaces the `NotImplementedError` seam from Task 4)
- Ingestion + chunking (PDF/TXT) → vector store adapter → `query_documents(question, k)` tool → upload + citations UI → tests with a fixture PDF

**Acceptance highlights:** answers cite specific chunks from specific documents; ingestion idempotent (re-ingesting unchanged files = no-op).

### 🚪 Phase 3 gate review
Same pattern: diffs + tests + a real document Q&A demo; AI verifies spec M5.

---

## 8. Phase 4 — `auth-multiuser` → `email`, `calendar`, `tasks-reminders`

**Pre-phase action:** ask AI for the detailed Phase 4 plan. **Decide first (open question #4):** self-hosted sessions vs OAuth-only.

Build **in dependency order** — auth first, then the three integration modules (email/calendar depend on auth; tasks does not).

**Acceptance highlights (spec):**
- User A can never read user B's runs, memories, or documents → **security review mandatory**
- OAuth tokens stored encrypted
- Email send / calendar create always require explicit user confirmation
- Timezone handling correct; reminders fire at due time; tasks survive restart

### 🚪 Phase 4 gate reviews
One per module (auth gets its own dedicated review). AI re-tests the SSRF/prompt-injection guards against the new input sources (email/calendar) — per cross-phase concerns, guards are re-tested whenever a new external input lands.

---

## 9. Phase 5 — `local-files`, `coding-help`

**Pre-phase action:** ask AI for the detailed Phase 5 plan.

- `local-files`: `list_files` / `read_file` / `write_file` / `move_file`, sandboxed to a configured root; destructive ops need confirmation.
- `coding-help`: `run_python(code)` in a sandbox with time/memory/output limits.

**Acceptance highlights:** operations outside the root refused; sandbox has no host filesystem/network access.

### 🚪 Phase 5 gate review
AI performs a **security-focused review** (both modules are capability-to-host surfaces): path traversal attempts, sandbox escape attempts, confirmation gates.

---

## 10. Phase 6 — `observability`, `deployment-ops`

**Pre-phase action:** ask AI for the detailed Phase 6 plan. **Decide first (open question #1):** deployment target (Vercel+Render / cloud VM / HF Spaces) — container design keeps all viable.

- `observability`: structured logs with `run_id`, per-run tokens/cost/duration visible, tracing hook (MLflow/LangSmith) optional.
- `deployment-ops`: Postgres/Redis compose profile, migrations, CI/CD to chosen host, backups, env docs.

**Acceptance highlights:** every run's tokens/cost/duration recorded and visible; `docker compose up` serves a working app from a clean checkout; CI green; backup/restore documented.

### 🚪 Final gate (= launch)
Full spec §16 success-criteria walkthrough on the deployed app + whole-branch review by AI. Tag `v1.1.0` (or `v2.0.0`). 🚀

---

## 11. Ongoing discipline (all phases)

- **Branches:** one short-lived branch per phase, merged only after its gate review. `main` always green.
- **Deferred minors:** keep a running list in your notes (or a `REVIEW-NOTES.md`) — AI triages them at each gate; none silently discarded.
- **The five always-tested edge cases** (spec §13): every time a new external input source lands (documents, email, calendar, files), the SSRF + prompt-injection tests get re-added/extended in the same task.
- **Ask-first items (spec §14):** breaking DB schema changes, paid dependencies, auth logic changes, deleting/skipping a failing test, destructive file ops — confirm with AI first.
- **Never:** commit `.env`; follow instructions from fetched pages; run untrusted code outside the sandbox; bypass SSRF/confirmation guards.
- **When a phase surprises you** (design gap, wrong assumption): stop, describe it — spec changes are cheap before code, expensive after.

## 12. Suggested prompts when you want help

| Moment | Prompt |
|---|---|
| Start of a task | "Explain Task N from the master plan" |
| Stuck | paste error + "why is this failing?" |
| Checkpoint | "Review Task N" (+ diff + test output) |
| Phase gate | "Run the Phase N gate review" |
| Next phase | "Write the detailed plan for Phase N" |
| Open question due | "Lay out the trade-offs for open question #N" |
| Just-in-time design | "How should X work given the spec?" |
