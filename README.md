# Atlas

Atlas is a personal AI assistant platform: one web app where you talk to an assistant that can research the web, answer questions about your documents, remember things, and (later) help with email, calendar, tasks, coding, and local files. Every capability plugs into a capability-agnostic core as a registered module, so the assistant grows without rewrites. The first shipped capability is the **Research Assistant** — ask a question, watch it plan → search → read → write in real time, and get back a Markdown report whose claims trace to working citations.

## Prerequisites

- Python >= 3.11 (venv)
- Node.js 18+
- Docker (optional, for containerized runs)

## Local development

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
```

## Docker

```bash
docker compose up --build        # run backend + frontend
docker compose config            # validate compose
```

## Configuration

Copy `.env.example` to `.env` (git-ignored) and fill in values. Switching the LLM (local ↔ openai ↔ mistral) and search provider (tavily ↔ duckduckgo) is an environment-only change — no code edits.

## Docs

- Spec: `docs/superpowers/specs/2026-10-09-atlas-master-spec.md`
- Master plan: `docs/superpowers/plans/2026-10-09-atlas-master-plan.md`
- Build roadmap: `docs/superpowers/plans/2026-10-09-atlas-build-roadmap.md`
