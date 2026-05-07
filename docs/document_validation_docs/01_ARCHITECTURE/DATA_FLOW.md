# Data Flow — Shapes and Transformations Through the Pipeline

This document shows the exact data shape at each stage boundary. Every transformation is explicit. Anyone reading this should be able to implement or test any stage independently.

---

## Input: API Request

```
POST /validate-document
Content-Type: multipart/form-data

project_id:     "3fa85f64-5717-4562-b3fc-2c963f66afa6"
schema_id:      "wine_lab_report"
schema_version: "v1.2"
document:       <binary PDF content>
```

---

## Stage Boundary 1 — After Block Extraction

**Type**: `list[TextBlock]`

```json
[
  {
    "id": "b0",
    "page": 1,
    "bbox": [57.0, 72.0, 538.0, 91.0],
    "text": "Wine Quality Analysis Report",
    "section_label": null
  },
  {
    "id": "b1",
    "page": 1,
    "bbox": [57.0, 110.0, 200.0, 125.0],
    "text": "Chemical Analysis",
    "section_label": null
  },
  {
    "id": "b2",
    "page": 1,
    "bbox": [57.0, 130.0, 300.0, 145.0],
    "text": "pH: 3.42",
    "section_label": "Chemical Analysis"
  },
  {
    "id": "b3",
    "page": 1,
    "bbox": [57.0, 150.0, 300.0, 165.0],
    "text": "Alcohol content: 11.2%",
    "section_label": "Chemical Analysis"
  },
  {
    "id": "b4",
    "page": 1,
    "bbox": [57.0, 170.0, 300.0, 185.0],
    "text": "Quality score: 6",
    "section_label": "Chemical Analysis"
  }
]
```

**Notes**:
- `section_label` is `null` for headings themselves; blocks under a heading inherit it.
- IDs are globally sequential across all pages (`b0`, `b1`, ..., `bN`).
- `bbox` is `[x0, y0, x1, y1]` in page coordinate points (origin top-left).

---

## Stage Boundary 2 — After Discovery Pass

**Type**: `list[ExtractionCandidate]`

```json
[
  {
    "field": "ph",
    "value": 3.42,
    "source": "regex",
    "confidence": 0.95,
    "block_id": "b2",
    "page": 1,
    "evidence_text": "pH: 3.42",
    "bbox": [57.0, 130.0, 300.0, 145.0],
    "section_label": "Chemical Analysis"
  },
  {
    "field": "ph",
    "value": 3.42,
    "source": "layout",
    "confidence": 0.55,
    "block_id": "b2",
    "page": 1,
    "evidence_text": "pH: 3.42",
    "bbox": [57.0, 130.0, 300.0, 145.0],
    "section_label": "Chemical Analysis"
  },
  {
    "field": "alcohol",
    "value": 11.2,
    "source": "regex",
    "confidence": 0.95,
    "block_id": "b3",
    "page": 1,
    "evidence_text": "Alcohol content: 11.2%",
    "bbox": [57.0, 150.0, 300.0, 165.0],
    "section_label": "Chemical Analysis"
  },
  {
    "field": "quality",
    "value": 6.0,
    "source": "regex",
    "confidence": 0.95,
    "block_id": "b4",
    "page": 1,
    "evidence_text": "Quality score: 6",
    "bbox": [57.0, 170.0, 300.0, 185.0],
    "section_label": "Chemical Analysis"
  }
]
```

**Notes**:
- All extractors contribute to the same flat list. No deduplication yet.
- Multiple candidates per field are normal (regex and layout both found pH).
- Values are typed (float, str, date) by the extractor — not raw strings.

---

## Stage Boundary 3 — After Schema Mapping

**Type**: `FieldCandidateMap` (dict)

Assuming schema declares fields: `ph`, `alcohol`, `quality`

```json
{
  "ph": {
    "status": "found",
    "candidates": [
      { "value": 3.42, "source": "regex", "confidence": 0.95, "block_id": "b2", ... },
      { "value": 3.42, "source": "layout", "confidence": 0.55, "block_id": "b2", ... }
    ]
  },
  "alcohol": {
    "status": "found",
    "candidates": [
      { "value": 11.2, "source": "regex", "confidence": 0.95, "block_id": "b3", ... }
    ]
  },
  "quality": {
    "status": "found",
    "candidates": [
      { "value": 6.0, "source": "regex", "confidence": 0.95, "block_id": "b4", ... }
    ]
  }
}
```

**Example: AMBIGUOUS case** (two different values for same field):

```json
{
  "temperature": {
    "status": "ambiguous",
    "candidates": [
      { "value": 18.5, "source": "regex", "confidence": 0.95, "block_id": "b7", "section_label": "Fermentation", ... },
      { "value": 22.0, "source": "regex", "confidence": 0.92, "block_id": "b19", "section_label": "Bottling", ... }
    ]
  }
}
```

**Example: MISSING case**:

```json
{
  "volatile_acidity": {
    "status": "missing",
    "candidates": []
  }
}
```

**Notes**:
- Candidates with identical values (same field, same value) are collapsed — counted as `found`, not `ambiguous`.
- `discovered_extras` (candidates for fields not in schema) are stored separately in the snapshot but do not appear in this map.

---

## Stage Boundary 4 — After Gap-Fill Pass

Gap-fill only modifies entries where `status = "missing"`. Other entries are unchanged.

```json
{
  "volatile_acidity": {
    "status": "found",
    "candidates": [
      {
        "value": 0.7,
        "source": "llm",
        "confidence": 0.4,
        "block_id": "b0",
        "page": 1,
        "evidence_text": "Volatile acidity was measured at 0.70 g/L",
        "bbox": null,
        "section_label": null
      }
    ]
  }
}
```

If gap-fill also fails to find a value, `status` remains `"missing"` → downstream validation will produce a `required` error.

---

## Stage Boundary 5 — After Inconsistency Check

**Type**: `InconsistencyReport`

```json
{
  "has_ambiguity": false,
  "ambiguous_fields": []
}
```

**Example with ambiguity**:

```json
{
  "has_ambiguity": true,
  "ambiguous_fields": [
    {
      "field": "temperature",
      "count": 2,
      "candidates": [
        { "value": 18.5, "source": "regex", "evidence_text": "Fermentation temp: 18.5°C", "block_id": "b7", "page": 1, "bbox": [...] },
        { "value": 22.0, "source": "regex", "evidence_text": "Bottling temperature 22.0°C", "block_id": "b19", "page": 2, "bbox": [...] }
      ]
    }
  ]
}
```

---

## Stage Boundary 6 — After Resolution

**Type**: `ResolvedDocument`

```json
{
  "ph": {
    "value": 3.42,
    "evidence": {
      "text": "pH: 3.42",
      "block_id": "b2",
      "page": 1,
      "bbox": [57.0, 130.0, 300.0, 145.0]
    }
  },
  "alcohol": {
    "value": 11.2,
    "evidence": {
      "text": "Alcohol content: 11.2%",
      "block_id": "b3",
      "page": 1,
      "bbox": [57.0, 150.0, 300.0, 165.0]
    }
  },
  "quality": {
    "value": 6.0,
    "evidence": {
      "text": "Quality score: 6",
      "block_id": "b4",
      "page": 1,
      "bbox": [57.0, 170.0, 300.0, 185.0]
    }
  }
}
```

**Notes**:
- Exactly one value per field.
- Evidence is the winning candidate's evidence (the one selected by resolution priority).
- Ambiguous fields are NOT present in `ResolvedDocument` — they are handled separately by the AMBIGUOUS status path.

---

## Stage Boundary 7 — After Validation Engine

**Type**: `list[ValidationError]`

**PASS example** (no errors):
```json
[]
```

**FAIL example**:
```json
[
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
```

---

## Final Output: API Response

**PASS**:
```json
{
  "status": "PASS",
  "schema_id": "wine_lab_report",
  "schema_version": "v1.2",
  "results": []
}
```

**FAIL**:
```json
{
  "status": "FAIL",
  "schema_id": "wine_lab_report",
  "schema_version": "v1.2",
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
    }
  ]
}
```

**AMBIGUOUS**:
```json
{
  "status": "AMBIGUOUS",
  "schema_id": "wine_lab_report",
  "schema_version": "v1.2",
  "results": [],
  "ambiguous_fields": [
    {
      "field": "temperature",
      "count": 2,
      "candidates": [
        {
          "value": 18.5,
          "source": "regex",
          "evidence": { "text": "Fermentation temp: 18.5°C", "block_id": "b7", "page": 1, "bbox": [...] }
        },
        {
          "value": 22.0,
          "source": "regex",
          "evidence": { "text": "Bottling temperature 22.0°C", "block_id": "b19", "page": 2, "bbox": [...] }
        }
      ]
    }
  ]
}
```

---

## Run Snapshot (Milestone 2)

The full internal state persisted to the `validation_runs` table:

```json
{
  "run_id": "uuid",
  "project_id": "uuid",
  "schema_key": "wine_lab_report",
  "schema_version": "v1.2",
  "pdf_hash": "sha256:abc123...",
  "created_at": "2026-05-02T09:00:00Z",
  "snapshots": {
    "blocks": [ ... ],
    "candidates": [ ... ],
    "field_candidate_map": { ... },
    "inconsistency_report": { ... },
    "resolved_document": { ... },
    "validation_report": { ... }
  }
}
```

---

## Cross-References

| Topic | Document |
|-------|----------|
| Stage algorithms | `01_ARCHITECTURE/PIPELINE_DESIGN.md` |
| ExtractionCandidate model | `03_DOMAIN/EXTRACTION_MODEL.md` |
| Resolution algorithm | `03_DOMAIN/RESOLUTION_MODEL.md` |
| Full API spec | `05_IMPLEMENTATION/API_SPEC.md` |
| Run persistence (M2) | `02_MILESTONES/MILESTONE_2_AUDITABILITY.md` |
