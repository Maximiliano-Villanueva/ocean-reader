# Wine Dataset Pipeline — End-to-End Flow

## Overview

This document describes the complete data flow from the raw wine CSV to a passing or failing test assertion. It is the concrete instantiation of the testing strategy for Milestone 1.

```
wine_quality.csv
      │
      ▼
[Row selection] ──────────────────────────────────┐
      │                                            │
      ▼                                            ▼
[LLM: generate clean HTML]       [LLM: generate noisy HTML]
      │                                            │
      ▼                                            ▼
[Playwright: HTML → clean PDF]   [Playwright: HTML → noisy PDF]
      │                                            │
      ▼                                            ▼
[ground truth JSON]              [ground truth JSON]
      │                                            │
      └────────────────┬───────────────────────────┘
                       │
                       ▼
              corpus_index.json
                       │
                       ▼ (at test time — no regeneration)
              [pytest parametrize over corpus]
                       │
                       ▼
              [run_wine_pdf_validation(pdf_bytes, schema_body)]
                       │
                       ▼
              [assert result.status == expected_status]
              [assert result.errors match expected_errors]
```

---

## Row Selection Strategy

50 rows are selected from the wine CSV to form the test corpus. Selection ensures coverage of all test case categories:

| Category | Count | Selection criteria |
|----------|-------|--------------------|
| All fields within range | 20 | `ph` ∈ [2.5,4.5], `alcohol` ∈ [8,15], `quality` ∈ [0,10] |
| Alcohol out of range | 10 | `alcohol > 15.0` or `alcohol < 8.0` |
| pH at boundary | 5 | `ph` exactly at min or max |
| Quality at boundary | 5 | `quality` = 0 or 10 |
| Unusual combinations | 10 | Rows with multiple close-to-boundary values |

Each selected row generates 2 documents (clean + noisy) → 100 total PDFs.

---

## Schema Used

All wine corpus tests use this schema (stored as `tests/fixtures/wine/schema.json`):

```json
{
  "fields": {
    "ph": {
      "type": "number",
      "required": true,
      "min": 2.5,
      "max": 4.5,
      "aliases": ["pH", "Measured pH", "pH level", "ph value"]
    },
    "alcohol": {
      "type": "number",
      "required": true,
      "min": 8.0,
      "max": 15.0,
      "aliases": ["Alcohol", "Alcohol %", "Alcohol content", "EtOH", "Alc.", "alcohol content"]
    },
    "quality": {
      "type": "number",
      "required": true,
      "min": 0,
      "max": 10,
      "aliases": ["Quality", "Quality score", "Panel rating", "Average quality score"]
    }
  },
  "rules": ["required", "range_validation"]
}
```

---

## Test Execution

### Parametrized test

```python
# tests/domain/validation/test_pipeline_wine_csv_fixtures.py

import json
from pathlib import Path
import pytest

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "wine"

def load_corpus():
    index = json.loads((FIXTURES_DIR / "corpus_index.json").read_text())
    return [
        (entry["path"], entry["expected_status"])
        for entry in index["entries"]
    ]

@pytest.mark.parametrize("fixture_path,expected_status", load_corpus())
def test_wine_corpus_fixture(fixture_path, expected_status, wine_schema_body):
    pdf_path = FIXTURES_DIR / f"{fixture_path}.pdf"
    gt_path = FIXTURES_DIR / f"{fixture_path}.json"

    pdf_bytes = pdf_path.read_bytes()
    ground_truth = json.loads(gt_path.read_text())

    # Run pipeline (LLM disabled in tests)
    report = run_wine_pdf_validation_sync(
        pdf_bytes,
        schema_body=wine_schema_body,
        schema_key="wine_lab_report",
        version_label="v1.0",
        llm_fallback=False,
    )

    assert report.status == expected_status, (
        f"Fixture {fixture_path}: expected {expected_status}, got {report.status}. "
        f"Errors: {report.errors}"
    )

    if expected_status == "FAIL":
        error_fields = {e.field for e in report.errors}
        for expected_error in ground_truth["expected_errors"]:
            assert expected_error["field"] in error_fields, (
                f"Expected error on field '{expected_error['field']}' not found. "
                f"Got errors: {report.errors}"
            )
```

### Evidence validation

Every error in a FAIL result must have evidence pointing to actual document content:

```python
def test_wine_fail_evidence_completeness(fixture_path, wine_schema_body):
    # ... run pipeline ...
    for error in report.errors:
        if error.rule != "required":  # required errors have no evidence
            assert error.evidence is not None, f"Missing evidence for {error.field}"
            assert error.evidence["text"], f"Empty evidence text for {error.field}"
            assert error.evidence["block_id"], f"Missing block_id for {error.field}"
            assert error.evidence["page"] >= 1, f"Invalid page for {error.field}"
```

---

## Determinism Test

A specific test verifies that running the same PDF twice produces identical results:

```python
def test_pipeline_is_deterministic(sample_pdf_bytes, wine_schema_body):
    results = [
        run_wine_pdf_validation_sync(sample_pdf_bytes, schema_body=wine_schema_body, ...)
        for _ in range(3)
    ]
    assert all(r.status == results[0].status for r in results)
    assert all(r.errors == results[0].errors for r in results)
```

---

## Noise Robustness Test

The noisy variants specifically test that irrelevant numbers in the document don't pollute extraction:

```python
def test_noisy_matches_clean(csv_row_idx, wine_schema_body):
    """Clean and noisy variants of the same row must produce the same result."""
    clean_pdf = load_fixture_pdf(f"clean/row_{csv_row_idx:03d}_clean.pdf")
    noisy_pdf = load_fixture_pdf(f"noisy/row_{csv_row_idx:03d}_noisy.pdf")

    clean_result = run_pipeline(clean_pdf, wine_schema_body)
    noisy_result = run_pipeline(noisy_pdf, wine_schema_body)

    assert clean_result.status == noisy_result.status
    assert clean_result.errors == noisy_result.errors
```

---

## Success Criteria for the Wine Pipeline

The pipeline is considered working when:

1. **PASS accuracy**: ≥ 95% of clean PASS documents correctly return PASS
2. **FAIL accuracy**: 100% of documents with out-of-range values return FAIL with correct field identified
3. **Noise resistance**: ≥ 90% of noisy documents return the same result as their clean counterpart
4. **Evidence completeness**: 100% of FAIL errors have non-null evidence (except `required`)
5. **Determinism**: 100% — same input always produces same output

---

## Cross-References

| Topic | Document |
|-------|----------|
| Dataset source and structure | `04_TESTING/DATASET_STRATEGY.md` |
| Generator script spec | `04_TESTING/TEST_GENERATOR_SPEC.md` |
| Test cases | `04_TESTING/TEST_CASES.md` |
| Test strategy | `04_TESTING/TEST_STRATEGY.md` |
