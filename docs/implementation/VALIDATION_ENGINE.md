# Document Validation Engine

Product direction: **schema-driven validation**, not conversational RAG. See [`adr/001-validation-engine-pivot.md`](adr/001-validation-engine-pivot.md).

## Code map (backend)

| Concern | Location |
|---------|----------|
| Schema lifecycle rules (active / archived / deleted) | `ocean_read/domain/validation/lifecycle.py` |
| Deterministic ensemble resolution | `ocean_read/domain/validation/resolution.py` |
| PASS/FAIL + structured errors | `ocean_read/domain/validation/engine.py` |
| DB model | `ocean_read/db/models.py` → `ValidationSchema` |
| Persistence port | `ocean_read/application/ports/validation_schema_repository.py` |
| SQLAlchemy adapter | `ocean_read/infrastructure/persistence/validation_schema_sqlalchemy.py` |

## Persistence rules

- **Create**: new row with `version_label`, `body` JSONB.
- **Update**: **never mutate** an immutable version — insert a **new row** with incremented `version_label` and optionally archive the previous **active** row.
- **Archive**: `status=archived`, `archived_at` set — **excluded** from validation resolver.
- **Delete**: soft-delete (`status=deleted`, `deleted_at`) — not usable.

## HTTP API

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/projects/{project_id}/validation-schemas` | List schema keys and versions for the UI |
| POST | `/api/validate-document` | Multipart: `project_id`, `schema_id`, `schema_version`, `document` (PDF) |

Router: `ocean_read/api/routers/validation.py`. Pipeline orchestration: `ocean_read/services/validation_pipeline.py`.

## PDF pipeline order

1. **PyMuPDF** layout blocks (`ocean_read/domain/validation/pdf_blocks.py`).
2. Ensemble extractors (`ocean_read/domain/validation/extractors_wine.py`) — extend with new document types via domain code, not user regex.
3. Optional **Ollama** LLM fallback (`VALIDATION_LLM_FALLBACK_ENABLED`).
4. Resolution + validation (`resolution.py`, `engine.py`).

## Legacy ingestion

Corpus ingestion, Airflow dispatch, and chat/agent pipelines **have been removed** from this repository. Postgres may still contain legacy tables from older migrations.
