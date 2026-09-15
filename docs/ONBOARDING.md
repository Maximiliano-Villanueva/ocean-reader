# Onboarding

Start here if you are new to Ocean Read (engineer, QA, or AI agent).

## What this product does

Ocean Read validates **supplier PDFs** against **versioned checklists** (JSON schemas). Each run returns **PASS**, **FAIL**, or **AMBIGUOUS**, with **evidence** (page, bounding box, matched text) for auditors and finance teams.

Canonical vocabulary: [`CONTEXT.md`](../CONTEXT.md). Product brief: [`project_definition.md`](../project_definition.md).

## Quick start (Docker — recommended)

### Prerequisites

1. [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Compose v2).
2. [Ollama](https://ollama.com) on the host for optional LLM features (schema assistant, open-ended fields, vision fallback):

```bash
ollama pull gemma4:e4b
```

### Run the stack

From the repository root:

```bash
cp .env.example .env   # adjust ports if needed
./start.sh             # or: docker compose up --build
```

Open the app: **http://localhost:8080/** (override port with `GATEWAY_HTTP_PORT` in `.env`).

Migrations run automatically on backend startup. API docs: **http://localhost:8080/docs**.

### First walkthrough in the UI

1. **Workspaces** — create a workspace (e.g. your lab or AP team name).
2. **Checklists** — browse or create a checklist version (Schema Studio wizard or JSON editor). Publish an active version.
3. **Validate** — upload PDFs, optionally add **tags** (batch, vendor, region), pick checklist + version, run validation.
4. **History** — filter by outcome, checklist, or filename; open any run for field table + PDF highlights.
5. **Insights** — save cohort views (tags + checklist filters), set a pass-rate threshold, preview aggregated results.

Optional: use the **schema agent** (Checklists → guided authoring) when the `schema-agent` service and Ollama are running. See [`implementation/SCHEMA_AGENT.md`](implementation/SCHEMA_AGENT.md).

## Local development (without full Docker UI)

### Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -U pip setuptools wheel
pip install -e ".[dev,docling]"
export DATABASE_URL=postgresql+asyncpg://ocean:ocean@127.0.0.1:15432/ocean_read
alembic upgrade head
uvicorn ocean_read.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev    # proxies /api to localhost:8000
```

### Tests

```bash
cd backend && pytest -q
```

Integration tests that need Postgres are skipped when `DATABASE_URL` is unset. See [`implementation/TESTING.md`](implementation/TESTING.md).

## Where to change code

| Task | Location |
|------|----------|
| Validation rules / extraction | `backend/src/ocean_read/domain/validation/` |
| Pipeline orchestration | `backend/src/ocean_read/services/validation_pipeline.py` |
| HTTP API | `backend/src/ocean_read/api/routers/` |
| React UI | `frontend/src/pages/`, `frontend/src/components/` |
| Schema authoring agent | `schema_agent/` |
| Insights / cohorts | `cohorts.py`, `cohort_aggregation.py`, `ProjectInsightsPage.tsx` |

## Documentation index

| Document | Purpose |
|----------|---------|
| [`implementation/ARCHITECTURE.md`](implementation/ARCHITECTURE.md) | System view |
| [`implementation/BACKEND.md`](implementation/BACKEND.md) | Python package map |
| [`implementation/FRONTEND.md`](implementation/FRONTEND.md) | Routes and API client |
| [`implementation/DOCKER.md`](implementation/DOCKER.md) | Compose, Traefik, env vars |
| [`implementation/VALIDATION_ENGINE.md`](implementation/VALIDATION_ENGINE.md) | Pipeline and persistence |
| [`implementation/SCHEMA_STUDIO.md`](implementation/SCHEMA_STUDIO.md) | Checklist editor UX |
| [`implementation/SCHEMA_AGENT.md`](implementation/SCHEMA_AGENT.md) | ADK schema assistant |
| [`document_validation_docs/README.md`](document_validation_docs/README.md) | Domain specs and ADRs |

## Reset dev data

| Goal | Command |
|------|---------|
| Wipe DB volumes + uploads | `docker compose down -v` then `./start.sh` |
| Empty validation rows only | `./scripts/empty_dev_database.sh` |
| Empty DB + upload files | `./scripts/empty_dev_testing.sh` |
