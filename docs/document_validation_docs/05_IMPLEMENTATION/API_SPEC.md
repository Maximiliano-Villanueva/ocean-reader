# API Specification

## Base URL

`/api` (all routes are prefixed)

**Local dev**: `http://localhost:8000/api`
**Docker**: `http://localhost:8080/api` (proxied through gateway)

---

## Authentication

Currently: no authentication on API routes (development mode). The gateway layer (`infra/gateway-auth/`) handles auth in production.

---

## Common Response Patterns

### Error response

```json
{
  "detail": "Human-readable error message"
}
```

| HTTP Status | Meaning |
|-------------|---------|
| `400` | Bad request (missing/invalid fields) |
| `404` | Resource not found |
| `409` | Conflict (e.g. schema not active) |
| `413` | Payload too large |
| `422` | Validation error (Pydantic) |

---

## Tag: System

### `GET /health`

Health check endpoint.

**Response** `200`:
```json
{ "status": "ok" }
```

---

## Tag: Workspace

### `GET /projects`

List all projects for the default organization.

**Response** `200`:
```json
[
  {
    "id": "uuid",
    "name": "Wine QA",
    "organization_id": "uuid",
    "created_at": "2026-05-01T10:00:00Z"
  }
]
```

---

### `POST /projects`

Create a new project.

**Request body** (JSON):
```json
{ "name": "Wine QA" }
```

**Response** `201`:
```json
{
  "id": "uuid",
  "name": "Wine QA",
  "organization_id": "uuid",
  "created_at": "2026-05-01T10:00:00Z"
}
```

---

### `GET /projects/{project_id}`

Get project by ID.

**Response** `200`: Same as `POST /projects` response.
**Response** `404`: Project not found.

---

## Tag: Validation

### `GET /projects/{project_id}/validation-schemas`

List all validation schemas for a project, grouped by schema key.

**Path params**:
- `project_id: UUID`

**Response** `200`:
```json
[
  {
    "schema_key": "wine_lab_report",
    "versions": [
      {
        "id": "uuid",
        "version_label": "v1.0",
        "status": "archived",
        "archived_at": "2026-04-01T00:00:00Z",
        "created_at": "2026-03-01T00:00:00Z"
      },
      {
        "id": "uuid",
        "version_label": "v1.1",
        "status": "active",
        "archived_at": null,
        "created_at": "2026-04-01T00:00:00Z"
      }
    ]
  }
]
```

---

### `POST /projects/{project_id}/validation-schemas`

Create a new schema version (and archive any existing active version for the same key).

**Path params**:
- `project_id: UUID`

**Request body** (JSON):
```json
{
  "schema_key": "wine_lab_report",
  "version_label": "v1.2",
  "body": {
    "fields": {
      "ph": { "type": "number", "required": true, "min": 3.0, "max": 4.5 },
      "alcohol": { "type": "number", "required": true, "min": 8.0, "max": 15.0 },
      "quality": { "type": "number", "required": true, "min": 0, "max": 10 }
    },
    "rules": ["required", "range_validation"]
  }
}
```

**Response** `201`:
```json
{ "id": "uuid" }
```

**Response** `422`: Schema body validation failed.
**Response** `409`: Version label already exists for this schema key.

---

### `PATCH /projects/{project_id}/validation-schemas/{schema_id}/archive`

Archive a specific schema version manually.

**Path params**:
- `project_id: UUID`
- `schema_id: UUID`

**Response** `204`: No content.
**Response** `404`: Schema not found.
**Response** `409`: Schema is already archived or deleted.

---

### `DELETE /projects/{project_id}/validation-schemas/{schema_id}`

Soft-delete a schema version.

**Path params**:
- `project_id: UUID`
- `schema_id: UUID`

**Response** `204`: No content.
**Response** `404`: Schema not found.

---

### `POST /validate-document`

Run the full validation pipeline on a PDF document.

**Request**: `multipart/form-data`

| Field | Type | Description |
|-------|------|-------------|
| `project_id` | UUID | The project context |
| `schema_id` | string | The schema key (e.g. `"wine_lab_report"`) |
| `schema_version` | string | The version label (e.g. `"v1.1"`) |
| `document` | file | PDF file (`application/pdf`) |

**Constraints**:
- Maximum file size: 30MB
- File must be `application/pdf` or have `.pdf` extension
- Schema version must be `active`

**Response** `200` — PASS:
```json
{
  "status": "PASS",
  "schema_id": "wine_lab_report",
  "schema_version": "v1.1",
  "results": []
}
```

**Response** `200` — FAIL:
```json
{
  "status": "FAIL",
  "schema_id": "wine_lab_report",
  "schema_version": "v1.1",
  "results": [
    {
      "field": "alcohol",
      "value": 18.0,
      "expected": [8.0, 15.0],
      "rule": "range_validation",
      "evidence": {
        "text": "Alcohol content: 18.0%",
        "block_id": "b3",
        "page": 1,
        "bbox": [57.0, 150.0, 300.0, 165.0]
      }
    },
    {
      "field": "volatile_acidity",
      "value": null,
      "expected": "present",
      "rule": "required",
      "evidence": null
    }
  ]
}
```

**Response** `200` — AMBIGUOUS:
```json
{
  "status": "AMBIGUOUS",
  "schema_id": "wine_lab_report",
  "schema_version": "v1.1",
  "results": [],
  "ambiguous_fields": [
    {
      "field": "temperature",
      "count": 2,
      "candidates": [
        {
          "value": 18.5,
          "source": "regex",
          "confidence": 0.95,
          "evidence": {
            "text": "Fermentation temp: 18.5°C",
            "block_id": "b7",
            "page": 1,
            "bbox": [57.0, 200.0, 400.0, 215.0]
          }
        },
        {
          "value": 22.0,
          "source": "regex",
          "confidence": 0.92,
          "evidence": {
            "text": "Bottling temperature 22.0°C",
            "block_id": "b19",
            "page": 2,
            "bbox": [57.0, 100.0, 400.0, 115.0]
          }
        }
      ]
    }
  ]
}
```

**Response** `400`: Missing schema_id or schema_version.
**Response** `404`: Schema version not found.
**Response** `409`: Schema version is not active.
**Response** `413`: PDF exceeds size limit.

---

### `POST /projects/{project_id}/schemas/generate` (Future)

Generate a schema body from a natural language description using LLM assistance.

**Request body** (JSON):
```json
{
  "description": "I need to validate wine lab reports. The report must have pH between 3.0 and 4.5, alcohol content between 8% and 15%, and a quality score from 0 to 10."
}
```

**Response** `200`:
```json
{
  "schema_body": {
    "fields": {
      "ph": { "type": "number", "required": true, "min": 3.0, "max": 4.5 },
      "alcohol": { "type": "number", "required": true, "min": 8.0, "max": 15.0 },
      "quality": { "type": "number", "required": true, "min": 0, "max": 10 }
    },
    "rules": ["required", "range_validation"]
  },
  "summary": "Schema with 3 required numeric fields: ph (3.0–4.5), alcohol (8.0–15.0%), quality (0–10)."
}
```

The response is a draft only. The client must call `POST /projects/{project_id}/validation-schemas` to persist it.

---

## Tag: Audit (Milestone 2)

### `GET /projects/{project_id}/validation-runs`

List validation runs for a project, most recent first.

**Query params**:
- `schema_key: string` (optional filter)
- `status: string` (optional: `PASS | FAIL | AMBIGUOUS`)
- `limit: int` (default 50, max 200)
- `offset: int` (default 0)

**Response** `200`:
```json
{
  "total": 142,
  "items": [
    {
      "run_id": "uuid",
      "schema_key": "wine_lab_report",
      "schema_version": "v1.1",
      "status": "FAIL",
      "pdf_hash": "sha256:abc123...",
      "created_at": "2026-05-01T14:30:00Z"
    }
  ]
}
```

---

### `GET /projects/{project_id}/validation-runs/{run_id}`

Get the full snapshot of a validation run.

**Response** `200`:
```json
{
  "run_id": "uuid",
  "project_id": "uuid",
  "schema_key": "wine_lab_report",
  "schema_version": "v1.1",
  "status": "FAIL",
  "pdf_hash": "sha256:abc123...",
  "created_at": "2026-05-01T14:30:00Z",
  "report": {
    "status": "FAIL",
    "results": [ ... ],
    "ambiguous_fields": []
  },
  "snapshots": {
    "blocks_count": 24,
    "candidates_count": 18,
    "resolved_fields": ["ph", "alcohol", "quality"]
  }
}
```

Full snapshot detail (`blocks`, `candidates`, etc.) available via separate sub-resource endpoints for performance:

- `GET /projects/{project_id}/validation-runs/{run_id}/blocks`
- `GET /projects/{project_id}/validation-runs/{run_id}/candidates`
- `GET /projects/{project_id}/validation-runs/{run_id}/resolved`

---

## Tag: Logs (Dev Only)

### `GET /logs`

Stream recent structured logs. Available only in non-production environments.

---

## OpenAPI

The full OpenAPI spec is auto-generated by FastAPI and available at:
- `/docs` — Swagger UI
- `/redoc` — ReDoc
- `/openapi.json` — raw JSON spec

---

## Cross-References

| Topic | Document |
|-------|----------|
| Response type definitions | `backend/src/ocean_read/schemas/__init__.py` |
| Validation pipeline service | `05_IMPLEMENTATION/PIPELINE_IMPLEMENTATION.md` |
| Schema DSL | `03_DOMAIN/VALIDATION_SCHEMA.md` |
| Run snapshot format | `01_ARCHITECTURE/DATA_FLOW.md` |
