# Ocean Read

**Schema-driven PDF validation** for QC, accounts payable, and audit teams. Upload a PDF, run it against a versioned checklist, and get **PASS / FAIL / AMBIGUOUS** with **pinpoint evidence** on every field.

## Features

- **Workspaces** — isolate projects (labs, AP desks, pilots).
- **Checklists** — versioned validation schemas (DSL v3), Schema Studio wizard, optional schema agent.
- **Validate** — batch PDF upload with optional **tags** (key/value or key-only).
- **History** — audit trail with filters, exports (CSV/JSON), PDF replay with highlights.
- **Insights** — cohort views: aggregate pass rates by tags, checklist, version, and outcome thresholds.
- **Manual corrections** — edit extracted values on a run; saves a new revision and revalidates.

## Quick start

### 1. Prerequisites

- Docker Desktop (Compose v2)
- [Ollama](https://ollama.com) on the host (optional but recommended for schema agent and LLM-assisted extraction):

```bash
ollama pull gemma4:e4b
```

### 2. Start the stack

```bash
git clone git@github.com:Maximiliano-Villanueva/ocean-reader.git
cd ocean-reader
cp .env.example .env
./start.sh
```

App URL: **http://localhost:8080/** (set `GATEWAY_HTTP_PORT` in `.env` to change).

| URL | Purpose |
|-----|---------|
| http://localhost:8080/ | Web UI |
| http://localhost:8080/docs | OpenAPI (Swagger) |
| http://localhost:8080/logs | Container logs viewer |
| http://127.0.0.1:5050/ | pgAdmin (credentials in `.env.example`) |
| `postgresql://ocean:ocean@127.0.0.1:15432/ocean_read` | Postgres from host |

### 3. Use the product

1. Create a **workspace**.
2. Open **Checklists** → create or publish a checklist version.
3. **Validate** → upload PDFs, add tags if needed, run batch validation.
4. Open results from **History** or aggregate them in **Insights**.

Primary API endpoint: `POST /api/validate-document` (multipart: `project_id`, `schema_id`, `schema_version`, `document`, optional `attributes` JSON).

## Development

### Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,docling]"
export DATABASE_URL=postgresql+asyncpg://ocean:ocean@127.0.0.1:15432/ocean_read
alembic upgrade head
uvicorn ocean_read.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend && npm install && npm run dev
```

### Tests

```bash
cd backend && pytest -q
```

Regenerate invoice test PDFs (synthetic data, no PII):

```bash
cd backend && uv run python tests/fixtures/invoice/generate_invoice_fixtures.py
```

## Documentation

| Document | Audience |
|----------|----------|
| **[`docs/ONBOARDING.md`](docs/ONBOARDING.md)** | Start here |
| [`CONTEXT.md`](CONTEXT.md) | Domain vocabulary |
| [`docs/implementation/ARCHITECTURE.md`](docs/implementation/ARCHITECTURE.md) | System design |
| [`docs/implementation/DOCKER.md`](docs/implementation/DOCKER.md) | Compose and env |
| [`docs/implementation/TESTING.md`](docs/implementation/TESTING.md) | pytest layout |
| [`AGENTS.md`](AGENTS.md) | Guidance for AI coding agents |

## Repository layout

```
backend/          FastAPI app (ocean_read/)
frontend/         Vite + React SPA
schema_agent/     Optional ADK schema authoring service
docs/             Architecture, domain specs, onboarding
infra/            Traefik, gateway-auth
scripts/          Dev helpers and E2E runners
```

## Reset / maintenance

```bash
docker compose down -v          # destroy DB + upload volumes
./scripts/empty_dev_database.sh   # clear validation rows, keep volumes
```

## Notes

- Legacy RAG/chat features were removed; the product is validation-first.
- Test fixtures use **synthetic** invoice and lab-report PDFs under `backend/tests/fixtures/`.
- Persona UX screenshots under `docs/personas/captures/` are local-only (gitignored).
