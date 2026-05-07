# MILESTONE 1 — VALIDATION MVP (EXECUTION SPEC)

## 1. Objective

Deliver a fully deterministic, end-to-end document validation system.

The system must:

- accept a PDF document
- extract structured data
- resolve ambiguities deterministically
- validate against a schema
- return **PASS**, **FAIL**, or **AMBIGUOUS** (when a field cannot be resolved to a single value)
- provide evidence for applicable decisions and a durable audit trail for each run

This milestone defines the minimum viable system that proves the product works.

**Implementation reference**: canonical response shape is `ValidateDocumentResponse` in `backend/src/ocean_read/schemas/__init__.py`. **Checklist / closure**: [`docs/project_management/M1_CHECKLIST.md`](../../project_management/M1_CHECKLIST.md).

---

## 2. Scope

### Included

- PDF ingestion
- block-based parsing (layout-aware)
- structured extraction (ensemble approach)
- deterministic resolution
- schema-based validation
- evidence mapping
- API endpoint for validation
- minimal frontend for interaction
- dataset-driven testing (wine dataset)

---

### Excluded

- chat interfaces
- RAG systems
- document search
- advanced rule DSL

---

### Included (UI / persistence — M1 product shell)

- **Validation history**: each successful `POST /api/validate-document` persists a **`validation_runs`** row (outcome, schema key/version, full JSON report, optional PDF path under `UPLOAD_ROOT`).
- **Paged history API**: `GET /api/projects/{id}/validation-runs?page=&page_size=` (default **25**, max **25**).
- **Schema lifecycle**: soft-delete a version via `DELETE /api/projects/{id}/validation-schemas/{schema_id}`.
- **Frontend**: dedicated routes for **history table**, **runner**, **schemas**, **flat versions**, and **run detail** with rule narrative + PDF replay when stored.

---

### Formerly excluded (now in scope for M1 UX closure)

- ~~validation history persistence~~ → **in scope** (see above)
- ~~analytics~~ → still out of scope

---

## 3. System Overview

Pipeline:

PDF → Block Extraction → Candidate Extraction → Resolution → Validation → Result + Evidence

---

## 4. API surface

POST /api/validate-document (multipart)

**Persistence**: each successful validation inserts **`validation_runs`** and returns **`run_id`** in the JSON body.

### List history

GET /api/projects/{project_id}/validation-runs?page=1&page_size=25

(max **25** rows per page)

### Detail + PDF

GET /api/projects/{project_id}/validation-runs/{run_id}

GET /api/projects/{project_id}/validation-runs/{run_id}/document — serves stored PDF when present.

---

## 5. Output Contract

`POST /api/validate-document` returns JSON matching **`ValidateDocumentResponse`**. Summary of fields:

| Field | Purpose |
|-------|---------|
| `status` | `"PASS"` \| `"FAIL"` \| `"AMBIGUOUS"` |
| `schema_id`, `schema_version` | Schema key and version label used for this run |
| `results` | **Failures only** — each item is one violated rule with `field`, `value`, `expected`, `rule`, optional `evidence` |
| `ambiguous_fields` | Present when `status === "AMBIGUOUS"`: `field`, `candidate_count` per ambiguous field |
| `schema_snapshot` | Full schema JSON body applied (immutable snapshot for audit UI) |
| `resolved_values` | Map of field name → resolved value after extraction/resolution (`null` when ambiguous or not reached) |
| `field_rule_outcomes` | Full **pass/fail ledger**: each global rule × field (`passed`, `value`, `expected`, optional `evidence`) |
| `run_id` | UUID string of the persisted **`validation_runs`** row (set after insert) |

Example (**FAIL** with one range violation; illustrative — arrays may be empty):

```json
{
  "status": "FAIL",
  "schema_id": "wine_lab_report",
  "schema_version": "1.0",
  "results": [
    {
      "field": "alcohol",
      "value": 18,
      "expected": "range 8-15",
      "rule": "range_validation",
      "evidence": {
        "text": "Alcohol: 18%",
        "block_id": "b12",
        "page": 1,
        "bbox": [100, 200, 300, 220],
        "section_label": null
      }
    }
  ],
  "ambiguous_fields": [],
  "schema_snapshot": {
    "fields": {},
    "rules": ["required", "range_validation", "type_check"]
  },
  "resolved_values": { "ph": 3.4, "alcohol": 18, "quality": 6 },
  "field_rule_outcomes": [
    {
      "field": "ph",
      "rule": "range_validation",
      "passed": true,
      "value": 3.4,
      "expected": "[2.5, 4.5]",
      "evidence": null
    },
    {
      "field": "alcohol",
      "rule": "range_validation",
      "passed": false,
      "value": 18,
      "expected": "[8.0, 15.0]",
      "evidence": { "text": "Alcohol: 18%", "block_id": "b12", "page": 1 }
    }
  ],
  "run_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

Persisted **`validation_runs.report`** stores the same payload (so history/detail APIs replay schema version, ledger, and snapshot without recomputation).

---

## 6. PDF Parsing (Block Extraction)

### Requirements

- use PyMuPDF
- extract text blocks with:
  - text
  - page number
  - bounding box

### Output

List of blocks:

{
  "block_id": "b0",
  "text": "...",
  "page": 1,
  "bbox": [...]
}

---

## 7. Extraction Layer (Ensemble)

### Goal

Extract candidate values for each field.

### Techniques

1. Regex extraction
2. Layout heuristics
3. LLM fallback (optional)

---

### Rules

- all candidates must include:
  - value
  - source (regex | layout | llm)
  - confidence
  - evidence reference (block_id)

---

## 8. Resolution Engine

### Goal

Select ONE value per field deterministically.

### Priority

regex > layout > llm

---

### Logic

- choose highest priority source
- if multiple candidates:
  - choose highest confidence
  - if tie → deterministic ordering (e.g. first occurrence)

---

### Output

{
  "alcohol": {
    "value": 11.2,
    "source": "regex",
    "evidence": {...}
  }
}

---

## 9. Validation Engine

### Input

Resolved document (JSON)

---

### Supported Rules

Global rule IDs (from schema `rules[]`) include:

#### 1. Required (`required`)

- field must exist when marked required

#### 2. Range Validation (`range_validation`)

- numeric value must be within `[min, max]` when field defines bounds

#### 3. Type Check (`type_check`)

- value must match declared field `type` (`number`, `string`, `date`)

---

### Output

- **Errors**: list of validation failures (also exposed as `results` on the API)
- **Outcomes**: full pass/fail matrix per field × rule (`field_rule_outcomes`) for audit and UI

---

## 10. Evidence Layer

For **each failing check** where extraction tied the value to PDF content, evidence SHOULD include:

- extracted text
- `block_id`
- page
- optional bbox and `section_label`

Some outcomes (e.g. **required** / missing field) may omit block-level evidence when nothing was extracted.

---

### Constraints

- evidence must map to actual PDF content when present
- no synthetic or inferred evidence for placement

---

## 11. Schema System

### Structure

{
  "fields": {
    "ph": { "type": "number", "required": true },
    "alcohol": { "type": "number", "min": 8, "max": 15 }
  }
}

---

### Lifecycle

- active → used for validation
- archived → not used
- deleted → not accessible

---

## 12. Frontend Requirements

### Routes (per project)

| Route | Purpose |
|-------|---------|
| `/projects/:id/validation` | Paginated **history** table (document name, schema, version, outcome, timestamp); link to detail. |
| `/projects/:id/validation/run` | **Runner** — schema/version selectors, PDF queue, immediate PASS/FAIL/AMBIGUOUS + preview. |
| `/projects/:id/validation/runs/:runId` | **Detail** — human-readable rule explanations, evidence, PDF replay if stored. |
| `/projects/:id/schemas` | Install default schema, **create** version, **delete** version (soft). |
| `/projects/:id/schema-versions` | Flat, paginated list of all versions (same data; alternate layout). |

### Output display

- PASS / FAIL / AMBIGUOUS indicator
- **Applied schema**: `schema_id` / `schema_version` plus optional **`schema_snapshot`** (full JSON)
- **Extracted values**: **`resolved_values`** when available
- **Rule ledger**: **`field_rule_outcomes`** (every rule × field, passes and failures); **`results`** remains the failure-only list
- Rule codes mapped to **professional descriptions** on the run detail page
- Evidence (text, block id, page, bbox / section where applicable)
- PDF preview when the run has a stored file  
  Older persisted runs may lack snapshot/ledger fields; UI falls back to legacy **`results`** only.

---

## 13. Testing Strategy (Mandatory)

System MUST be validated using dataset-driven testing.

---

### Dataset

Wine Quality Dataset (CSV)

---

### Test Generation

For each row:

- generate 2 HTML documents:
  - clean (only relevant data)
  - noisy (same data + noise)

---

### Pipeline

CSV → HTML (LLM) → PDF (Playwright) → Validation

---

### Rules

- LLM temperature = 0
- generated HTML must be stored
- PDFs must be reused (no regeneration in tests)

---

## 14. Test Cases

### PASS

- valid document → PASS

### FAIL

- missing field
- out of range
- invalid format / wrong type

### AMBIGUOUS

- conflicting or tied candidates so no single resolved value per field (pipeline returns before full validation)

---

## 15. Determinism Requirements

System MUST guarantee:

- same input → same output
- no randomness in validation
- LLM only used as fallback with fixed parameters

---

## 16. Observability (audit trail vs runtime logs)

**M1 satisfies traceability primarily via persistence**, not full structured application logging:

- **`validation_runs`** stores **`outcome`**, **`report`** (full API-shaped JSON: failures, ambiguous fields, **`schema_snapshot`**, **`resolved_values`**, **`field_rule_outcomes`**), and optional PDF path — sufficient to reconstruct **what was extracted**, **which schema version applied**, and **pass/fail per rule**.
- **Structured pipeline logs** (extraction candidates, resolution choices, stdout JSON events) are specified in [`../07_OPERATIONS/LOGGING_STRATEGY.md`](../07_OPERATIONS/LOGGING_STRATEGY.md); wiring **every** event at **INFO** remains **follow-up work** and is tracked in [`docs/project_management/M1_CHECKLIST.md`](../../project_management/M1_CHECKLIST.md) under CI/ops hardening.

---

## 17. Definition of Done

Milestone is complete when:

- API returns correct validation results **including** PASS / FAIL / AMBIGUOUS, persisted **`run_id`**, and audit fields (**`schema_snapshot`**, **`resolved_values`**, **`field_rule_outcomes`**) for new runs
- frontend displays validation, evidence, schema snapshot, extracted values, and rule ledger on run detail (with fallback for older rows)
- tests run automatically and pass (see [`docs/project_management/M1_CHECKLIST.md`](../../project_management/M1_CHECKLIST.md))
- system is deterministic for the non-LLM path
- no manual inspection required to trust the synthetic corpus regression suite

**Ops note**: optional CI target — Postgres + migrations + API tests with **zero skips** — is documented as checklist tech debt, not a blocker for functional M1 closure.

---

## 18. Success Criteria

- system correctly validates synthetic PDF dataset
- noisy documents do not break extraction
- all failures are explained with evidence
- system behavior is reproducible

---

## 19. Non-Goals

- conversational UX
- general document understanding
- probabilistic validation
- AI-first decision making

---

## 20. Key Principle

This system is NOT an AI assistant.

It is a deterministic validation engine with controlled AI assistance.