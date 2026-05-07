# Logging Strategy — Structured Logs for Validation Runs

## Principles

1. **Structured logging only**: All log output is JSON. No unstructured print statements in production code.
2. **Pipeline traceability**: Every log entry for a validation run includes `run_id`, `project_id`, `schema_key`, and `schema_version` where available.
3. **Log at decision points**: Log when a meaningful decision is made (which candidate won resolution, which rule failed), not when trivial code executes.
4. **No PII in logs**: PDF content, user data, and document text are never logged in full. Evidence text snippets are truncated at 200 characters.
5. **LLM calls are always logged**: Every LLM invocation is logged with its input length, output length, and latency — regardless of whether it produced useful output.

---

## Log Levels

| Level | Usage |
|-------|-------|
| `DEBUG` | Internal pipeline state — candidate counts, block counts, resolution choices. Only relevant during development. |
| `INFO` | Pipeline lifecycle — run started, PASS/FAIL/AMBIGUOUS result. Always emitted. |
| `WARNING` | Unexpected but recoverable — LLM call failed (fallback to no-LLM), schema field not found after gap-fill, run persistence failed. |
| `ERROR` | Unrecoverable — pipeline exception, schema fetch failure. |

---

## Log Events Reference

### Run Lifecycle

```json
{
  "event": "validation_run_started",
  "level": "info",
  "run_id": "uuid",
  "project_id": "uuid",
  "schema_key": "wine_lab_report",
  "schema_version": "v1.1",
  "pdf_hash": "sha256:abc123...",
  "pdf_size_bytes": 45230,
  "timestamp": "2026-05-02T09:00:00.123Z"
}
```

```json
{
  "event": "validation_run_completed",
  "level": "info",
  "run_id": "uuid",
  "project_id": "uuid",
  "schema_key": "wine_lab_report",
  "schema_version": "v1.1",
  "status": "FAIL",
  "error_count": 2,
  "ambiguous_count": 0,
  "duration_ms": 342,
  "timestamp": "2026-05-02T09:00:00.465Z"
}
```

---

### Block Extraction

```json
{
  "event": "blocks_extracted",
  "level": "debug",
  "run_id": "uuid",
  "block_count": 24,
  "page_count": 2,
  "duration_ms": 45
}
```

---

### Discovery Pass

```json
{
  "event": "discovery_pass_completed",
  "level": "debug",
  "run_id": "uuid",
  "candidate_count": 18,
  "by_source": {
    "regex": 12,
    "layout": 6
  },
  "by_field": {
    "ph": 2,
    "alcohol": 2,
    "quality": 2
  }
}
```

---

### Schema Mapping

```json
{
  "event": "schema_mapping_completed",
  "level": "debug",
  "run_id": "uuid",
  "found_fields": ["ph", "alcohol", "quality"],
  "missing_fields": [],
  "ambiguous_fields": []
}
```

When ambiguity is detected:

```json
{
  "event": "ambiguity_detected",
  "level": "info",
  "run_id": "uuid",
  "field": "temperature",
  "candidate_count": 2,
  "values": [18.5, 22.0],
  "sections": ["Fermentation", "Bottling"]
}
```

---

### Gap-Fill Pass

```json
{
  "event": "gap_fill_started",
  "level": "debug",
  "run_id": "uuid",
  "missing_fields": ["volatile_acidity"]
}
```

```json
{
  "event": "gap_fill_completed",
  "level": "debug",
  "run_id": "uuid",
  "resolved_by_gap_fill": ["volatile_acidity"],
  "still_missing": []
}
```

---

### Resolution

```json
{
  "event": "field_resolved",
  "level": "debug",
  "run_id": "uuid",
  "field": "alcohol",
  "winner_source": "regex",
  "winner_confidence": 0.95,
  "winner_block_id": "b3",
  "candidate_count": 3
}
```

---

### LLM Calls

Every LLM invocation is logged regardless of outcome:

```json
{
  "event": "llm_extraction_called",
  "level": "info",
  "run_id": "uuid",
  "field": "volatile_acidity",
  "model": "llama3",
  "temperature": 0.0,
  "input_chars": 4820,
  "duration_ms": 1230
}
```

On LLM failure:

```json
{
  "event": "llm_extraction_failed",
  "level": "warning",
  "run_id": "uuid",
  "field": "volatile_acidity",
  "error": "Connection refused",
  "action": "field_remains_missing"
}
```

---

### Validation Engine

```json
{
  "event": "validation_error",
  "level": "debug",
  "run_id": "uuid",
  "field": "alcohol",
  "rule": "range_validation",
  "value": 18.0,
  "expected": [8.0, 15.0],
  "evidence_block_id": "b3",
  "evidence_page": 1
}
```

---

### Run Persistence

```json
{
  "event": "run_persisted",
  "level": "info",
  "run_id": "uuid",
  "status": "FAIL"
}
```

On persistence failure (non-fatal):

```json
{
  "event": "run_persistence_failed",
  "level": "warning",
  "run_id": "uuid",
  "error": "database connection timeout",
  "action": "result_returned_to_caller_run_not_saved"
}
```

---

## Logger Names

| Module | Logger name |
|--------|------------|
| Pipeline service | `ocean_read.services.validation_pipeline` |
| LLM service | `ocean_read.services.validation_llm` |
| Extractor | `ocean_read.domain.validation.extractors` |
| Resolution | `ocean_read.domain.validation.resolution` |
| Engine | `ocean_read.domain.validation.engine` |
| API router | `ocean_read.api.routers.validation` |

---

## Log Format (Production)

```python
# ocean_read/main.py — configure at startup

import logging
import json

class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_dict = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S.%fZ"),
            "level": record.levelname.lower(),
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "extra"):
            log_dict.update(record.extra)
        return json.dumps(log_dict)
```

All structured fields are passed via the `extra` parameter:

```python
logger.info(
    "validation_run_completed",
    extra={
        "event": "validation_run_completed",
        "run_id": str(run_id),
        "status": report.status,
        "error_count": len(report.errors),
        "duration_ms": duration_ms,
    }
)
```

---

## Development Log Access

In development, the `GET /api/logs` endpoint (tag: Logs) streams recent structured log entries. This allows developers to inspect pipeline decisions without ssh-ing into a container.

The `services/docker_logs.py` service powers this endpoint. It is not available in production.

---

## Cross-References

| Topic | Document |
|-------|----------|
| Pipeline stages (what gets logged) | `01_ARCHITECTURE/PIPELINE_DESIGN.md` |
| LLM usage rules | `06_DECISIONS/ADR_003.md` |
| Run persistence (M2) | `02_MILESTONES/MILESTONE_2_AUDITABILITY.md` |
