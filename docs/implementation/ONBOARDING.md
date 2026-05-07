# Onboarding

Read this file first, then **[`CONTEXT.md`](../CONTEXT.md)** and **[`project_definition.md`](../project_definition.md)**.

## What you are building

A **deterministic document validation engine**: PDF in → extracted fields → schema rules → **PASS/FAIL** + **evidence**. Not a chat or RAG product.

## Running the stack

- **Docker (recommended):** `./start.sh` or `docker compose up --build` → app at **`http://localhost:8080/`** (see **`GATEWAY_HTTP_PORT`**).
- **Backend only:** `uvicorn ocean_read.main:app` from `backend/` after `pip install -e ".[dev]"` and `alembic upgrade head`.
- **Frontend only:** `npm run dev` in `frontend/` (proxies `/api` to port 8000 in Vite config).

## Where to change things

| Task | Location |
|------|----------|
| Validation rules / extraction | `ocean_read/domain/validation/`, `ocean_read/services/validation_pipeline.py` |
| Schema persistence | `ocean_read/infrastructure/persistence/validation_schema_sqlalchemy.py` |
| HTTP API | `ocean_read/api/routers/validation.py`, `workspace.py` |
| UI | `frontend/src/pages/ProjectValidationPage.tsx`, `frontend/src/api.ts` |
| Product direction | [`adr/001-validation-engine-pivot.md`](adr/001-validation-engine-pivot.md) |
| Milestone tracking | [`../project_management/MILESTONES.md`](../project_management/MILESTONES.md), [`../project_management/M1_CHECKLIST.md`](../project_management/M1_CHECKLIST.md) |

## Docs index

See **[`docs/README.md`](README.md)**.
