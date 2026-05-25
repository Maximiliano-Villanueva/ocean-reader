# MILESTONE 2 — AUDITABILITY & RUN HISTORY

## Objective

Add full persistence and auditability to the validation pipeline. After Milestone 2, every validation execution is recorded as an immutable snapshot (including intermediate pipeline state where applicable) and can be retrieved for debugging and compliance.

---

## Relationship to Milestone 1 (already shipped)

The following were implemented under **M1** as the product shell:

- `validation_runs` table with **`report`** JSONB (API-shaped outcome: `results`, `ambiguous_fields`, `schema_snapshot`, `resolved_values`, `field_rule_outcomes`, `run_id`)
- Optional **`pdf_relative_path`** for PDF replay under `UPLOAD_ROOT`
- **`GET /projects/{id}/validation-runs`** (paginated), **`GET .../validation-runs/{run_id}`**, **`GET .../validation-runs/{run_id}/document`**
- Frontend: **`/projects/:id/validation`** (history), **`/projects/:id/validation/runs/:runId`** (detail)

**Milestone 2 extends** this with **`pdf_hash`**, **`snapshots`** JSONB (intermediate pipeline state), **list filters**, **sub-resource GET endpoints**, and **snapshot serialization** tests.

---

## Scope

### Included

- `ValidationRun` persistence with **PDF SHA-256 fingerprint** (`pdf_hash`)
- JSONB **`snapshots`** — blocks, candidates, field map, inconsistency report, resolved document (see below)
- Run history API with **`schema_key`** and **`status`** (filters **`outcome`** column) query params
- Sub-resources: **`/blocks`**, **`/candidates`**, **`/resolved`**
- Run detail UI: **PDF fingerprint** display; history page **filters**
- **Round-trip-safe** snapshot serialization (`serialize_pipeline_snapshots` / tests)
- **Run history lifecycle (version history)**: operators can **archive** and/or **soft-delete** validation runs from the history UI, with matching API (`PATCH` / `DELETE` or equivalent) so rows are hidden from default lists while remaining recoverable for audit where policy requires it. Hard purge (GDPR-style) may be a separate admin-only action in a later milestone if needed.

### Excluded

- Run comparison UI (side-by-side diffing)
- Run export (PDF/CSV)
- Run alerting or notifications
- Schema change impact analysis across historic runs
- **PDF.js + bbox highlighting** — deferred to **Milestone 4** (Evidence-Centric UX); detail view keeps `<iframe>` PDF replay from M1

---

## What Gets Stored Per Run

Every successful **`POST /api/validate-document`** creates one `validation_runs` row (immutable after insert).

**Columns (implemented):**

| Column | Purpose |
|--------|---------|
| `id` | UUID primary key |
| `project_id` | Owning project |
| `validation_schema_id` | FK to schema row (nullable after delete) |
| `schema_key`, `version_label` | Schema identity used for the run |
| `document_filename` | Original upload name |
| **`outcome`** | `PASS` \| `FAIL` \| `AMBIGUOUS` |
| **`report`** | Full **`ValidateDocumentResponse`** JSON |
| **`pdf_hash`** | `sha256:{hex}` of uploaded bytes |
| **`snapshots`** | Intermediate pipeline JSON (nullable on legacy rows pre-M2) |
| `pdf_relative_path` | Optional stored PDF path |
| **`archived_at`** | When set, run is hidden from default history (audit retention) |
| **`deleted_at`** | Soft-delete timestamp; run hidden from default list until **restore** |
| Timestamps | `created_at`, `updated_at` |

**`snapshots` JSON shape** (`domain/validation/snapshot_serializer.py`):

```json
{
  "blocks": [ /* TextBlock dicts */ ],
  "candidates": [ /* ExtractionCandidate dicts */ ],
  "field_candidate_map": { "field_name": { "status": "found|missing|ambiguous", "candidates": [] } },
  "inconsistency_report": { "has_ambiguity": false, "ambiguous_fields": [] },
  "resolved_document": { "ph": 3.4, "alcohol": 12.0 }
}
```

The final validation verdict remains in **`report`** (not duplicated inside `snapshots`).

---

## PDF Hash

Implementation: **`ocean_read/domain/validation/pdf_hash.py`** — `compute_pdf_hash(data: bytes) -> str` → `sha256:{digest}`.

**Usage:**

- Compare fingerprints across runs (“same bytes?”).
- With unchanged code + same schema version, same hash implies reproducible pipeline behavior.

---

## Database

- **Migration `009_validation_runs_m2_audit`**: adds **`pdf_hash`** (non-null; legacy rows backfilled empty string before default removal), **`snapshots`** JSONB nullable, indexes on **`pdf_hash`**, **`(project_id, schema_key)`**, **`(project_id, outcome)`**.
- **Migration `010_validation_runs_lifecycle`**: adds **`archived_at`** and **`deleted_at`** (nullable) plus partial index for default list queries.

---

## API Surface

| Endpoint | Description |
|----------|-------------|
| `GET /projects/{id}/validation-runs?page=&page_size=` | Paginated list; optional **`schema_key`**, **`status`** (filters **`outcome`**); default omits archived/soft-deleted runs |
| `GET /projects/{id}/validation-runs?include_hidden=true` | Same list including archived and soft-deleted rows (audit recovery) |
| `PATCH /projects/{id}/validation-runs/{run_id}` | Body: **`restore`** (clear flags) and/or **`archived`** (bool) to archive/unarchive |
| `DELETE /projects/{id}/validation-runs/{run_id}` | Soft-delete run (sets **`deleted_at`**; recover via PATCH **`restore`**) |
| `GET /projects/{id}/validation-runs/{run_id}` | Detail including **`report`**, **`pdf_hash`**, **`archived_at`**, **`deleted_at`** |
| `GET /projects/{id}/validation-runs/{run_id}/blocks` | `snapshots.blocks` or `[]` if legacy |
| `GET /projects/{id}/validation-runs/{run_id}/candidates` | `snapshots.candidates` or `[]` |
| `GET /projects/{id}/validation-runs/{run_id}/resolved` | `snapshots.resolved_document` or `{}` |
| `GET /projects/{id}/validation-runs/{run_id}/document` | Stored PDF file when present |

---

## Frontend

| Route | Behavior |
|-------|----------|
| `/projects/:id/validation` | History table + **schema** / **outcome** filters; **Show archived / removed**; **Archive** / **Remove** / **Restore** per run |
| `/projects/:id/validation/runs/:runId` | Detail + **`pdf_hash`**; archive/remove when active; banner + **Restore** when hidden |

---

## Definition of Done

Milestone 2 is complete when:

- **`POST /api/validate-document`** persists **`pdf_hash`** and **`snapshots`** for new runs
- List endpoint supports **`schema_key`** and **`status`** filters with correct totals
- Sub-resource endpoints return snapshot slices (empty for legacy rows)
- Run detail exposes **`pdf_hash`**; history UI exposes filters
- Domain tests: **`pdf_hash`** determinism, **`snapshot_serializer`** JSON round-trip
- Integration tests (PostgreSQL + migrations): persistence + filters + sub-resources (`tests/api/test_validation_runs_m2.py`)
- **Run history lifecycle**: archive / soft-delete validation runs via API and history UI; default list excludes archived/deleted rows; recovery path documented for audit

---

## Cross-References

| Topic | Document |
|-------|----------|
| Pipeline | `05_IMPLEMENTATION/PIPELINE_IMPLEMENTATION.md` |
| API | `05_IMPLEMENTATION/API_SPEC.md` |
| Logging (runtime vs persistence) | `07_OPERATIONS/LOGGING_STRATEGY.md` |
| M1 checklist | `docs/project_management/M1_CHECKLIST.md` |
