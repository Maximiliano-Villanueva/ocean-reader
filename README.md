# Ocean Read

## What this is

**Ocean Read** is a **schema-driven deterministic PDF validation** service: projects hold **versioned validation schemas** (JSON rules); the API accepts a PDF and returns **PASS/FAIL** with **structured evidence** (matched text, block id, page, bbox). Optional **Ollama** LLM assists extraction internally (`VALIDATION_LLM_FALLBACK_ENABLED`); users never configure prompts or regex.

The canonical brief is **[`project_definition.md`](project_definition.md)**. Domain vocabulary: **[`CONTEXT.md`](CONTEXT.md)**.

## Quick links (Docker)

Defaults assume Compose / `.env`. Replace **8080** with **`GATEWAY_HTTP_PORT`** if overridden.

- **App:** [http://localhost:8080/](http://localhost:8080/)
- **Logs:** [http://localhost:8080/logs](http://localhost:8080/logs)
- **API docs:** `http://localhost:8080/docs` — primary validation endpoint **`POST /api/validate-document`**
- **pgAdmin:** `http://127.0.0.1:5050/` (see **`.env.example`** for credentials); DB host **`db`**, port **5432**, database **`ocean_read`**
- **Postgres from host:** `psql postgresql://ocean:ocean@127.0.0.1:15432/ocean_read` (or **`POSTGRES_PUBLISH`**)

### Reset database / volumes

| Goal | Command (repo root) |
|------|------------------------|
| Destroy Postgres + uploads volumes | `docker compose down -v` then `./start.sh` |
| Empty app rows (CASCADE from projects) | `./scripts/empty_dev_database.sh` |
| Same + wipe upload files | `./scripts/empty_dev_testing.sh` |

## Documentation

| Document | Purpose |
|----------|---------|
| **[`docs/ONBOARDING.md`](docs/ONBOARDING.md)** | First read for engineers and AI agents |
| [`docs/VALIDATION_ENGINE.md`](docs/VALIDATION_ENGINE.md) | Pipeline, schema persistence, API |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | System view (edge, backend, DB) |
| [`docs/BACKEND.md`](docs/BACKEND.md) | `ocean_read/` package layout |
| [`docs/FRONTEND.md`](docs/FRONTEND.md) | React routes and `api.ts` |
| [`docs/TESTING.md`](docs/TESTING.md) | `pytest` conventions |
| [`docs/DOCKER.md`](docs/DOCKER.md) | Compose, Traefik, env vars |
| [`docs/README.md`](docs/README.md) | Index of `docs/` |

## Quick start (Docker)

1. Install [Ollama](https://ollama.com) on the host and run `ollama pull gemma4:e4b` (LLM used when validation LLM fallback is enabled).

2. From repo root: **`./start.sh`** or `docker compose up --build`.

3. Open **[http://localhost:8080/](http://localhost:8080/)** → create a **project** → **Validation** tab → select schema version and PDF (schemas must exist in DB; see [`docs/VALIDATION_ENGINE.md`](docs/VALIDATION_ENGINE.md)).

## Local backend (no Docker)

Python **3.11+**.

```bash
cd backend && python3 -m venv .venv && source .venv/bin/activate
pip install -U pip setuptools wheel
pip install -e ".[dev]"
pytest -q
export DATABASE_URL=postgresql+asyncpg://ocean:ocean@127.0.0.1:15432/ocean_read
alembic upgrade head
uvicorn ocean_read.main:app --reload --host 0.0.0.0 --port 8000
```

```bash
cd frontend && npm install && npm run dev
```

## Repo layout

- `backend/` — FastAPI app package `ocean_read/`
- `frontend/` — Vite + React (`ProjectValidationPage`, projects)
- `docs/` — architecture and onboarding
- `infra/` — Traefik, optional gateway-auth, optional Airflow profile (not used by validation core)

## Notes

- Legacy **RAG/chat/ingestion** code paths were **removed**; Postgres may still contain old tables until you run a dedicated cleanup migration.
- **`EMBEDDING_DIMENSION`** must stay aligned with Alembic/pgvector definitions for the historical `chunks` table.
