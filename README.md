# Ocean Read

**Schema-driven PDF validation** for QC, accounts payable, and audit teams. Upload a PDF, run it against a versioned checklist, and get **PASS / FAIL / AMBIGUOUS** with **pinpoint evidence** on every field.

## Product tour

Ocean Read follows a simple loop: **define rules → validate documents → review evidence → aggregate batches**.

### 1. Checklists — versioned acceptance rules

Each workspace keeps immutable checklist versions. Publish a new version when specs change; older runs stay tied to the version that was active at the time.

![Checklists list with versioned Supplier Invoice and Wine Quality schemas](docs/screenshots/01-checklists.png)

### 2. Schema Studio — build rules, prompts, and cross-field logic

**Schema Studio** is where you configure what to extract and how to validate it:

- **Structured fields** — types, regex, labels, min/max, document roles
- **Open-ended (LLM) insights** — natural-language prompts for informative extraction
- **Cross-field rules** — e.g. `total_due == subtotal_before_tax + tax_amount`
- **Checklist assistant** — describe changes in plain language; optional sample PDF for context
- **Dry-run panel** — test against a sample PDF before publishing

![Schema Studio overview with outline, assistant, and dry-run panel](docs/screenshots/02-schema-studio-overview.png)

**Field rules** — pin extraction to PDF labels, regex patterns, and validation bounds:

![Field configuration for total_due with regex and document role](docs/screenshots/03-schema-field-rules.png)

**Assistant prompt** — add or refine rules without editing JSON:

![Checklist assistant with a natural-language cross-field rule prompt](docs/screenshots/04-schema-assistant-prompt.png)

**Open-ended prompts** — LLM-backed insights that do not affect PASS/FAIL unless you wire them into rules:

![Open-ended vendor_name insight with extraction prompt](docs/screenshots/05-schema-open-ended-prompt.png)

### 3. Validate — upload PDFs with tags

Pick a checklist version, optionally tag the batch (`batch`, `vendor`, `region`, …), drop one or more PDFs, and run validation. Tags flow into **Insights** for cohort reporting.

![Validate flow with checklist picker, tags, and PDF drop zone](docs/screenshots/06-validate-upload.png)

### 4. Results — field table + PDF highlights

Every run shows extracted values, rule outcomes, and a **source document** viewer. Click a row to jump to evidence on the PDF. Export CSV/JSON or apply **manual corrections** (creates a new revision and revalidates).

![FAIL run detail with field table and highlighted PDF evidence](docs/screenshots/07-validation-results.png)

### 5. Insights — cohort pass rates

Group runs by tags, checklist, version, and outcome. Set a pass-rate target, preview matching documents, and save views for recurring audits (e.g. monthly AP batches).

![Insights cohort with pass-rate banner and aggregated run table](docs/screenshots/08-insights-aggregate.png)

---

## Features at a glance

| Area | What you get |
|------|----------------|
| **Workspaces** | Isolated projects (labs, AP desks, pilots) |
| **Checklists** | Versioned DSL v3 schemas, Schema Studio, optional schema agent |
| **Validate** | Batch PDF upload with optional key/value tags |
| **History** | Audit trail, outcome filters, CSV/JSON export, PDF replay |
| **Insights** | Cohort views, pass-rate thresholds, saved filters |
| **Corrections** | Edit extracted values on a run; new revision + revalidation |

## Quick start

### Prerequisites

- Docker Desktop (Compose v2)
- [Ollama](https://ollama.com) on the host (optional; schema agent and LLM-assisted extraction):

```bash
ollama pull gemma4:e4b
```

### Start the stack

```bash
git clone git@github.com:Maximiliano-Villanueva/ocean-reader.git
cd ocean-reader
cp .env.example .env
./start.sh
```

App URL: **http://localhost:8080/** (override with `GATEWAY_HTTP_PORT` in `.env`).

| URL | Purpose |
|-----|---------|
| http://localhost:8080/ | Web UI |
| http://localhost:8080/docs | OpenAPI (Swagger) |
| http://localhost:8080/logs | Container logs viewer |
| http://127.0.0.1:5050/ | pgAdmin (credentials in `.env.example`) |
| `postgresql://ocean:ocean@127.0.0.1:15432/ocean_read` | Postgres from host |

### First run in the UI

1. Create a **workspace**.
2. **Checklists** → publish a checklist version (or use demo data after `./start.sh`).
3. **Validate** → upload PDFs, add tags if needed, run batch validation.
4. Open a result from **History**, or aggregate batches in **Insights**.

Primary API: `POST /api/validate-document` — multipart fields `project_id`, `schema_id`, `schema_version`, `document`, optional `attributes` JSON for tags.

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

Regenerate synthetic invoice test PDFs (no PII):

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
docs/             Architecture, domain specs, onboarding, screenshots
infra/            Traefik, gateway-auth
scripts/          Dev helpers and E2E runners
```

## Reset / maintenance

```bash
docker compose down -v              # destroy DB + upload volumes
./scripts/empty_dev_database.sh     # clear validation rows, keep volumes
```

## Notes

- Legacy RAG/chat features were removed; the product is validation-first.
- Test fixtures use **synthetic** invoice and lab-report PDFs under `backend/tests/fixtures/`.
- UI screenshots for the README live in [`docs/screenshots/`](docs/screenshots/). Persona UX captures under `docs/personas/captures/` are local-only (gitignored).
