# Domain Model — Entities, Aggregates, and Value Objects

## Overview

The domain is modeled using DDD (Domain-Driven Design) building blocks. This document defines every aggregate, entity, and value object, their invariants, and their relationships. The domain layer has zero I/O dependencies — all types here are pure Python dataclasses or Pydantic models with no SQLAlchemy, FastAPI, or LLM references.

---

## Aggregate 1 — Organization

**Type**: Aggregate Root

**Identity**: `organization_id: UUID`

**Fields**:
| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Stable, globally unique |
| `name` | str | Display name |
| `created_at` | datetime | Immutable after creation |

**Invariants**:
- Name must be non-empty.
- An organization cannot be deleted if it has active projects.

**Relationships**:
- Has many `Project` entities (one-to-many).

---

## Aggregate 2 — Project

**Type**: Entity (child of Organization)

**Identity**: `project_id: UUID`

**Fields**:
| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Stable, globally unique |
| `organization_id` | UUID | Parent organization (FK) |
| `name` | str | Display name |
| `settings` | dict | Extensible project-level config (JSON) |
| `created_at` | datetime | Immutable after creation |

**Invariants**:
- `organization_id` is set at creation and never changes.
- A project can have zero or more `ValidationSchema` versions.

---

## Aggregate 3 — ValidationSchema

**Type**: Aggregate Root

**Identity**: `(project_id, schema_key, version_label)` — composite unique key

**Fields**:
| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Surrogate key |
| `project_id` | UUID | Owning project |
| `schema_key` | str | Logical name (e.g. `"wine_lab_report"`) |
| `version_label` | str | Human-readable version (e.g. `"v1.2"`) |
| `status` | SchemaLifecycleStatus | `active \| archived \| deleted` |
| `body` | dict | The schema definition (DSL as JSON) |
| `created_at` | datetime | Immutable after creation |
| `archived_at` | datetime? | Set when status → archived |
| `deleted_at` | datetime? | Set when status → deleted (soft delete) |

**Invariants**:
- Only one version per `(project_id, schema_key)` can be `active` at a time. When a new version is created, the previously active version is automatically archived.
- Once archived or deleted, a version's `body` is immutable.
- Deleted versions are never physically removed — they remain in the database for audit.
- A deleted version cannot be used for validation (`can_use_for_validation(status)` returns `false`).

**Lifecycle state machine**:
```
           create
  ──────────────────▶ ACTIVE
                          │
                create new version
                          │
                          ▼
                      ARCHIVED ──── (soft delete) ──▶ DELETED
```

**Body structure** (see `03_DOMAIN/VALIDATION_SCHEMA.md` for full DSL spec):
```json
{
  "fields": {
    "alcohol": { "type": "number", "min": 8, "max": 15, "required": true }
  },
  "rules": ["required", "range_validation"]
}
```

---

## Aggregate 4 — ValidationRun (Milestone 2)

**Type**: Aggregate Root

**Identity**: `run_id: UUID`

**Fields**:
| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Stable, globally unique |
| `project_id` | UUID | Owning project |
| `schema_key` | str | Schema used |
| `schema_version` | str | Exact version label used |
| `pdf_hash` | str | SHA-256 of the input PDF (`"sha256:..."`) |
| `created_at` | datetime | When the run was executed |
| `status` | str | Final verdict: `PASS \| FAIL \| AMBIGUOUS` |
| `snapshots` | dict | Full intermediate state (see below) |

**Snapshot contents** (stored in `snapshots` JSONB field):
- `blocks`: serialized `list[TextBlock]`
- `candidates`: serialized `list[ExtractionCandidate]`
- `field_candidate_map`: serialized `FieldCandidateMap`
- `inconsistency_report`: serialized `InconsistencyReport`
- `resolved_document`: serialized `ResolvedDocument`
- `validation_report`: serialized `ValidationReport`

**Invariants**:
- A `ValidationRun` is **immutable** once created. It is never updated.
- The `pdf_hash` enables reproducibility: if the same PDF is submitted again, its run can be found and compared.
- All snapshot fields are present for every run (no partial snapshots).

---

## Value Object — TextBlock

**Immutable**. One unit of parsed PDF content.

| Field | Type | Description |
|-------|------|-------------|
| `id` | str | Stable `"b{n}"` ID, document-order sequential |
| `page` | int | 1-indexed page number |
| `bbox` | tuple[float,float,float,float] | `(x0, y0, x1, y1)` in page points |
| `text` | str | Concatenated, stripped text content |
| `section_label` | str \| None | Inferred parent section heading |

**Equality**: Two `TextBlock`s are equal if all fields are equal. The `id` field is stable for a given PDF — same PDF always produces same block IDs.

---

## Value Object — ExtractionCandidate

**Immutable**. One extractor's hypothesis about a field value, with full provenance.

| Field | Type | Description |
|-------|------|-------------|
| `field` | str | Field name this candidate is for |
| `value` | Any | Extracted value (typed: float, str, date) |
| `source` | str | `"regex" \| "layout" \| "llm"` |
| `confidence` | float | 0.0–1.0; used for tie-breaking |
| `block_id` | str | Source `TextBlock.id` |
| `page` | int | Source page |
| `evidence_text` | str | Exact text snippet that produced this value |
| `bbox` | tuple \| None | Bounding box of the evidence, if available |
| `section_label` | str \| None | Section where this was found |

---

## Value Object — EvidenceRef

**Immutable**. A pointer to a location in the source document.

| Field | Type | Description |
|-------|------|-------------|
| `text` | str | The text that was used as evidence |
| `block_id` | str | Source `TextBlock.id` |
| `page` | int | 1-indexed page |
| `bbox` | tuple \| None | Bounding box for visual highlighting |

---

## Value Object — ResolvedField

**Immutable**. A single resolved field value with its evidence.

| Field | Type | Description |
|-------|------|-------------|
| `value` | Any | The resolved value |
| `evidence` | EvidenceRef | Where it came from |

---

## Value Object — ValidationError

**Immutable**. A single rule violation.

| Field | Type | Description |
|-------|------|-------------|
| `field` | str | The field that violated a rule |
| `value` | Any | The actual value found (or None if missing) |
| `expected` | Any | What was expected (range, `"present"`, etc.) |
| `rule` | str | Rule identifier (e.g. `"range_validation"`) |
| `evidence` | EvidenceRef \| None | Where the value came from (None if missing) |

---

## Value Object — ValidationReport

**Immutable**. The final output of the pipeline.

| Field | Type | Description |
|-------|------|-------------|
| `status` | str | `"PASS" \| "FAIL" \| "AMBIGUOUS"` |
| `schema_key` | str \| None | Schema used |
| `schema_version` | str \| None | Version used |
| `errors` | tuple[ValidationError,...] | All rule violations |
| `ambiguous_fields` | tuple[AmbiguousField,...] | Fields with conflicting values |
| `extras` | tuple[ExtractionCandidate,...] | Discovered but not in schema |

---

## Value Object — AmbiguousField

**Immutable**. A field with two or more conflicting candidate values.

| Field | Type | Description |
|-------|------|-------------|
| `field` | str | The ambiguous field name |
| `count` | int | Number of conflicting candidates |
| `candidates` | tuple[ExtractionCandidate,...] | All conflicting candidates, with evidence |

---

## Value Object — SchemaLifecycleStatus

**Enum**:
```python
class SchemaLifecycleStatus(str, Enum):
    ACTIVE   = "active"
    ARCHIVED = "archived"
    DELETED  = "deleted"
```

**Rules**:
- `can_use_for_validation(status)` → True only for `ACTIVE`
- `is_accessible(status)` → True for `ACTIVE` and `ARCHIVED` (DELETED versions are hidden from API)

---

## Domain Events (Future)

These events are not yet implemented but are part of the intended model:

| Event | Trigger | Consumers |
|-------|---------|-----------|
| `DocumentValidated` | End of pipeline | Audit context (persist run), downstream integrations |
| `SchemaVersionActivated` | New schema version created | Notifications, cache invalidation |
| `AmbiguityDetected` | Inconsistency check finds conflicts | Human review queue (future) |

---

## Cross-References

| Topic | Document |
|-------|----------|
| Extraction model detail | `03_DOMAIN/EXTRACTION_MODEL.md` |
| Resolution algorithm | `03_DOMAIN/RESOLUTION_MODEL.md` |
| Schema DSL | `03_DOMAIN/VALIDATION_SCHEMA.md` |
| Rule engine | `03_DOMAIN/RULE_ENGINE.md` |
| Database models (infrastructure) | `05_IMPLEMENTATION/BACKEND_OVERVIEW.md` |
| Run persistence (M2) | `02_MILESTONES/MILESTONE_2_AUDITABILITY.md` |
