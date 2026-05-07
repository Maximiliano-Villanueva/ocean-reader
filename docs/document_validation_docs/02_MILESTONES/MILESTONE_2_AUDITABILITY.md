# MILESTONE 2 — AUDITABILITY & RUN HISTORY

## Objective

Add full persistence and auditability to the validation pipeline. After Milestone 2, every validation execution is recorded as an immutable snapshot and can be retrieved, compared, and reproduced.

---

## Scope

### Included

- `ValidationRun` persistence (full snapshot per run)
- PDF hash computation and storage
- Run history API endpoints
- Run detail UI (read-only view of a past run)
- Reproducibility guarantee (same PDF + same schema → same result)

### Excluded

- Run comparison UI (side-by-side diffing)
- Run export (PDF/CSV)
- Run alerting or notifications
- Schema change impact analysis across historic runs

---

## What Gets Stored Per Run

Every validation execution creates exactly one `ValidationRun` row. It is immutable once created.

```
ValidationRun {
  id:               UUID          — stable run identifier
  project_id:       UUID          — owning project
  schema_key:       string        — schema used
  schema_version:   string        — exact version label used
  pdf_hash:         string        — SHA-256 of the input PDF ("sha256:{hex}")
  status:           string        — PASS | FAIL | AMBIGUOUS
  created_at:       datetime      — UTC timestamp of execution
  snapshots: {
    blocks:               list[TextBlock]         — all extracted blocks
    candidates:           list[ExtractionCandidate] — all discovered candidates
    field_candidate_map:  FieldCandidateMap       — mapping result
    inconsistency_report: InconsistencyReport     — ambiguity check result
    resolved_document:    ResolvedDocument        — one value per field
    validation_report:    ValidationReport        — final result with errors
  }
}
```

**Why store intermediate snapshots?**
- Debugging: if the result changes after a code update, the intermediate states reveal exactly where the pipeline diverged.
- Auditability: a compliance officer can inspect every step of the reasoning chain.
- Reproducibility: the snapshot captures what the extractor found on the day of the run, independent of future changes.

---

## PDF Hash

The PDF is **not stored** (compliance, cost, privacy). Only its SHA-256 hash is stored.

```python
import hashlib

def compute_pdf_hash(data: bytes) -> str:
    digest = hashlib.sha256(data).hexdigest()
    return f"sha256:{digest}"
```

**Usage**:
- Lookup: "Has this exact PDF been validated before?" → query by `pdf_hash`.
- Reproducibility assertion: if you run the same PDF again and get the same `pdf_hash`, the result should be identical (given same schema version and same code).

---

## Database Changes

### New table: `validation_runs`

```sql
CREATE TABLE validation_runs (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id   UUID NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
  schema_key   VARCHAR(128) NOT NULL,
  schema_version VARCHAR(64) NOT NULL,
  pdf_hash     VARCHAR(71) NOT NULL,   -- "sha256:" (7) + 64 hex chars
  status       VARCHAR(32) NOT NULL,
  snapshots    JSONB NOT NULL,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_validation_runs_project ON validation_runs(project_id, created_at DESC);
CREATE INDEX idx_validation_runs_pdf_hash ON validation_runs(pdf_hash);
```

**Indexes**:
- `(project_id, created_at DESC)` — run history queries
- `(pdf_hash)` — deduplication lookup

---

## New Port (Application Layer)

```python
# ocean_read/application/ports/validation_run_repository.py

from abc import ABC, abstractmethod

class ValidationRunRepository(ABC):

    @abstractmethod
    async def save(self, run: ValidationRun) -> str:
        """Persist a new run. Returns run_id."""

    @abstractmethod
    async def get(self, project_id: str, run_id: str) -> ValidationRun | None:
        """Get a specific run by ID, scoped to project."""

    @abstractmethod
    async def list(
        self,
        project_id: str,
        *,
        schema_key: str | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[int, list[ValidationRunSummary]]:
        """List runs with optional filters. Returns (total_count, page)."""
```

---

## Pipeline Changes

The `ValidationPipelineService.run()` method gains two new steps:

1. **Before execution**: Compute `pdf_hash = compute_pdf_hash(pdf_bytes)`.
2. **After result assembly**: If a `run_repository` is injected, persist a `ValidationRun` snapshot.

The service should **not fail if persistence fails**. The validation result is returned to the caller regardless. The run-save failure is logged as a warning.

```python
# Pseudo-code in ValidationPipelineService.run():

pdf_hash = compute_pdf_hash(pdf_bytes)

# ... run all pipeline stages ...

report = assemble_report(...)

if self._run_repo and project_id:
    try:
        await self._run_repo.save(ValidationRun(
            project_id=project_id,
            schema_key=schema_key,
            schema_version=version_label,
            pdf_hash=pdf_hash,
            status=report.status,
            snapshots=serialize_snapshots(blocks, candidates, field_map, resolved, report),
        ))
    except Exception as e:
        logger.warning("Failed to persist validation run: %s", e)

return report
```

---

## New API Endpoints

See `05_IMPLEMENTATION/API_SPEC.md` for full contracts.

| Endpoint | Description |
|----------|-------------|
| `GET /projects/{id}/validation-runs` | List runs with filters |
| `GET /projects/{id}/validation-runs/{run_id}` | Get full run snapshot |
| `GET /projects/{id}/validation-runs/{run_id}/blocks` | Blocks sub-resource |
| `GET /projects/{id}/validation-runs/{run_id}/candidates` | Candidates sub-resource |
| `GET /projects/{id}/validation-runs/{run_id}/resolved` | Resolved document sub-resource |

---

## New Frontend Views

See `05_IMPLEMENTATION/FRONTEND_SPEC.md` for full UI specs.

| View | Description |
|------|-------------|
| `/projects/:id/runs` | Run history table with status badges |
| `/projects/:id/runs/:runId` | Run detail: read-only validation result + snapshot info |

**PDF viewer upgrade**: Milestone 2 is the target milestone for upgrading from `<iframe>` to a PDF.js-based viewer that supports bbox highlighting.

---

## Snapshot Serialization

Snapshots are stored as JSONB in PostgreSQL. Each intermediate state is serialized to a plain dict using a `snapshot_serializer` module:

```python
def serialize_snapshots(
    blocks: list[TextBlock],
    candidates: list[ExtractionCandidate],
    field_map: FieldCandidateMap,
    inconsistency_report: InconsistencyReport,
    resolved: ResolvedDocument,
    report: ValidationReport,
) -> dict:
    return {
        "blocks": [dataclasses.asdict(b) for b in blocks],
        "candidates": [dataclasses.asdict(c) for c in candidates],
        "field_candidate_map": serialize_field_map(field_map),
        "inconsistency_report": dataclasses.asdict(inconsistency_report),
        "resolved_document": serialize_resolved(resolved),
        "validation_report": dataclasses.asdict(report),
    }
```

**Deserialization** must be implemented for the run detail API endpoint so stored snapshots can be returned as structured JSON responses.

---

## Reproducibility Guarantee

The system guarantees that for a given `pdf_hash` + `schema_key` + `schema_version`:
- Running the validation again on the same PDF produces the same `ValidationReport`.
- This holds as long as the code has not changed (extractor behavior, resolution priority).

Code changes that affect extraction or resolution are **breaking changes** and should be tracked in ADRs. When such a change is deployed, historic runs may differ from a re-run of the same document.

The run snapshot captures the full intermediate state precisely so that discrepancies can be explained: "The 2026-04-01 run found value X in block b7; the 2026-05-01 run finds value Y because the regex pattern was changed."

---

## Definition of Done

Milestone 2 is complete when:

- Every call to `POST /validate-document` creates a `ValidationRun` row.
- `GET /projects/:id/validation-runs` returns runs correctly paginated.
- `GET /projects/:id/validation-runs/:run_id` returns the full snapshot.
- The run history UI is accessible and functional.
- Tests cover: run creation, run listing, run retrieval, snapshot completeness.
- Snapshot serialization is roundtrip-safe (serialize → store → deserialize → same data).

---

## Cross-References

| Topic | Document |
|-------|----------|
| ValidationRun domain model | `03_DOMAIN/DOMAIN_MODEL.md` |
| Pipeline orchestration | `05_IMPLEMENTATION/PIPELINE_IMPLEMENTATION.md` |
| API contracts | `05_IMPLEMENTATION/API_SPEC.md` |
| Frontend run history views | `05_IMPLEMENTATION/FRONTEND_SPEC.md` |
| Data flow (snapshot format) | `01_ARCHITECTURE/DATA_FLOW.md` |
