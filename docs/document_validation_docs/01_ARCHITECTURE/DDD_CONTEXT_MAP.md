# DDD Context Map — Ocean Read Document Validation Engine

## Overview

The system is divided into five bounded contexts. Each context owns its domain language, its data, and its rules. Contexts communicate through well-defined interfaces — they never share database tables directly or call each other's internal functions.

```
┌──────────────────────────────────────────────────────────────────────┐
│                         OCEAN READ SYSTEM                            │
│                                                                      │
│  ┌─────────────────────┐     ┌──────────────────────────────────┐   │
│  │  WORKSPACE CONTEXT  │────▶│  SCHEMA MANAGEMENT CONTEXT       │   │
│  │  Org, Project       │     │  ValidationSchema, versioning     │   │
│  └─────────────────────┘     └──────────────┬───────────────────┘   │
│                                             │ schema body            │
│  ┌──────────────────────────────────────────▼───────────────────┐   │
│  │            DOCUMENT PROCESSING CONTEXT                        │   │
│  │  PDF → TextBlock → ExtractionCandidate → FieldCandidateMap   │   │
│  └──────────────────────────────┬───────────────────────────────┘   │
│                                 │ FieldCandidateMap + schema         │
│  ┌──────────────────────────────▼───────────────────────────────┐   │
│  │            VALIDATION CONTEXT                                 │   │
│  │  Resolution → ValidationEngine → ValidationReport            │   │
│  └──────────────────────────────┬───────────────────────────────┘   │
│                                 │ ValidationReport                   │
│  ┌──────────────────────────────▼───────────────────────────────┐   │
│  │            AUDIT CONTEXT  (Milestone 2)                       │   │
│  │  ValidationRun, run history, snapshot persistence             │   │
│  └───────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Context 1 — Workspace

**Domain language**: Organization, Project, Member

**Responsibility**:
- Manages the multi-tenant structure: Organizations and their Projects.
- Enforces tenant isolation — all queries are scoped by `organization_id`.
- No validation logic lives here.

**Aggregates**:
- `Organization` (aggregate root)
- `Project` (entity, child of Organization)

**Key invariants**:
- A Project always belongs to exactly one Organization.
- Deleting an Organization cascades to all Projects and their Schemas.
- A Project can have zero or more ValidationSchemas.

**Interfaces exposed to other contexts**:
- `require_project(project_id)` — verifies a project exists and returns its `organization_id`. Called by Schema Management and Validation contexts.

---

## Context 2 — Schema Management

**Domain language**: ValidationSchema, SchemaKey, VersionLabel, SchemaBody, SchemaLifecycleStatus

**Responsibility**:
- Manages the definition of what a valid document looks like.
- Enforces schema versioning: every edit creates a new version; the previous active version is archived.
- Handles schema lifecycle: `active → archived → deleted`.
- Exposes schemas to the Validation context.

**Aggregates**:
- `ValidationSchema` (aggregate root)
  - Identity: `(project_id, schema_key, version_label)` — unique
  - Status: `active | archived | deleted`
  - Body: the schema definition (JSON/DSL)

**Key invariants**:
- Only one schema version per `(project_id, schema_key)` can be `active` at a time.
- Archived versions are immutable and auditable.
- Deleted versions are soft-deleted — never physically removed.

**Schema body structure** (see `03_DOMAIN/VALIDATION_SCHEMA.md` for full spec):
```json
{
  "fields": {
    "alcohol": { "type": "number", "min": 8, "max": 15, "required": true }
  },
  "rules": ["required", "range_validation"]
}
```

**Interfaces exposed**:
- `get_active_schema(project_id, schema_key)` → `SchemaBody`
- `get_schema_by_version(project_id, schema_key, version_label)` → `SchemaBody`
- `list_schemas_grouped(project_id)` → grouped list for UI

**Schema authoring flow** (LLM-assisted):
- User describes desired rules in natural language.
- LLM translates to schema DSL/JSON (temperature=0).
- User reviews and approves in UI before the schema is saved.
- See `05_IMPLEMENTATION/FRONTEND_SPEC.md` for the UI design.

---

## Context 3 — Document Processing

**Domain language**: TextBlock, ExtractionCandidate, SectionLabel, DiscoveryResult, FieldCandidateMap, ExtractionSource, InconsistencyReport

**Responsibility**:
- Converts raw PDF bytes into structured, field-level candidate values.
- Does not know about validation rules — only about what values exist in the document.
- Produces the full evidence trail for every candidate.

**Value objects**:
- `TextBlock` — immutable unit of parsed PDF content with geometry.
- `ExtractionCandidate` — one extractor's hypothesis about a field value, with evidence.
- `FieldCandidateMap` — per-field grouping of all candidates, with status (`found | missing | ambiguous`).
- `InconsistencyReport` — list of fields with conflicting values.

**Bounded context language note**: This context speaks "extraction" not "validation". It asks "what did I find in this document?" not "is this value correct?". The distinction is important for maintaining clean separation.

**Interfaces exposed**:
- `run_discovery(blocks, schema_field_names)` → `FieldCandidateMap`
- `run_gap_fill(blocks, missing_fields, schema_body)` → `list[ExtractionCandidate]`
- `check_inconsistencies(field_candidate_map)` → `InconsistencyReport`

---

## Context 4 — Validation

**Domain language**: ResolvedDocument, EvidenceRef, ValidationError, ValidationReport, ValidationRule

**Responsibility**:
- Takes a resolved, unambiguous document and checks it against schema rules.
- Produces the final PASS/FAIL/AMBIGUOUS verdict with full evidence.
- Pure domain logic — no I/O, no LLM, no database.

**Value objects**:
- `ResolvedDocument` — a flat map of `field → {value, evidence}` with one value per field.
- `ValidationError` — a single rule violation: field, value, expected, rule, evidence.
- `ValidationReport` — the final result: status, errors, ambiguous fields, extra discovered fields.

**Key invariant**: The validation engine is a pure function. It can be called with the same inputs as many times as needed and will always return the same result. It has no dependencies on infrastructure.

**Interfaces exposed**:
- `resolve_document(field_candidate_map)` → `ResolvedDocument` (deterministic)
- `validate(resolved_document, schema_body)` → `ValidationReport`

---

## Context 5 — Audit (Milestone 2)

**Domain language**: ValidationRun, RunSnapshot, PdfHash, RunStatus

**Responsibility**:
- Persists every validation execution as an immutable snapshot.
- Enables run history, replay, and comparison.
- No business logic — this context only stores and retrieves.

**Aggregates**:
- `ValidationRun` (aggregate root)
  - `run_id`: UUID
  - `project_id`, `schema_key`, `schema_version`
  - `pdf_hash`: SHA-256 of the input PDF
  - `blocks_snapshot`: JSON serialization of all `TextBlock`s
  - `candidates_snapshot`: JSON serialization of all `ExtractionCandidate`s
  - `resolved_snapshot`: JSON serialization of `ResolvedDocument`
  - `report_snapshot`: JSON serialization of `ValidationReport`
  - `created_at`: timestamp

**Key invariant**: Once created, a `ValidationRun` is never modified. It is an immutable audit record.

**Interfaces exposed**:
- `save_run(run)` → `run_id`
- `get_run(run_id)` → `ValidationRun`
- `list_runs(project_id, schema_key)` → `list[ValidationRunSummary]`

---

## Context Relationships

| Relationship | Type | Description |
|---|---|---|
| Workspace → Schema Management | **Customer/Supplier** | Workspace supplies `project_id` verification; Schema Management is the supplier of schema data |
| Schema Management → Document Processing | **Published Language** | Schema body (JSON DSL) is the shared language; Document Processing reads field names from it |
| Document Processing → Validation | **Published Language** | `FieldCandidateMap` is the interface; Validation consumes it |
| Validation → Audit | **Customer/Supplier** | Validation produces reports; Audit persists them |

---

## Anti-Corruption Layers

- **HTTP Layer → Application**: FastAPI request models are translated to domain types before entering the application layer. No FastAPI types leak into domain or application code.
- **Infrastructure → Domain**: SQLAlchemy models are never exposed to the domain layer. Repository methods return plain dicts or domain value objects.
- **LLM Provider → Domain**: LLM responses are parsed and validated before being converted to `ExtractionCandidate` objects. Raw LLM text never enters the domain.

---

## Cross-References

| Topic | Document |
|-------|----------|
| Domain entities detail | `03_DOMAIN/DOMAIN_MODEL.md` |
| Extraction model | `03_DOMAIN/EXTRACTION_MODEL.md` |
| Validation schema DSL | `03_DOMAIN/VALIDATION_SCHEMA.md` |
| Backend module map | `05_IMPLEMENTATION/BACKEND_OVERVIEW.md` |
