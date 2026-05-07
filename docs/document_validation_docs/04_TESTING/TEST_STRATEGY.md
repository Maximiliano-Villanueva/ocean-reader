# Test Strategy — Document Validation Engine

## 1. Objective

Define a deterministic, automated testing strategy that validates the full system behavior:

- block extraction
- ensemble extraction (regex, layout, LLM)
- schema mapping and inconsistency detection
- deterministic resolution
- validation rule evaluation
- evidence mapping
- API contracts

The goal is to eliminate manual testing and ensure:

- reproducibility — same input always produces same output
- correctness — results match known ground truth
- regression safety — a code change that changes behavior fails the test suite

---

## 2. Testing Principles

1. **All tests must be deterministic.** No random inputs, no random seeds, no time-dependent logic.
2. **LLM is disabled in unit and integration tests.** `validation_llm_fallback_enabled = false` in test config. LLM-specific behavior has its own isolated tests.
3. **Ground truth is explicit.** Every test knows what the correct answer is before running. There is no "golden file" that gets updated silently.
4. **No manual inspection.** If you need to read the output to decide if it's correct, the test is wrong.
5. **PDFs are fixtures.** Test PDFs are generated once and committed. Tests load them from disk — they never generate PDFs at test time.
6. **Domain tests have no fixtures.** Unit tests for domain logic (extraction, resolution, validation engine) use Python objects only — no PDFs, no database.

---

## 3. Test Layers

### Layer 1 — Unit Tests

**Scope**: Individual functions and classes in the domain layer.

**What is tested**:
- `parse_pdf_blocks` — given raw bytes (from fixture PDF), returns correct blocks
- `SchemaAwareExtractor.extract_regex` — given blocks and schema, returns correct candidates
- `resolve_field_candidate` — given candidates, picks correct winner
- `validate` (engine) — given resolved document and schema, returns correct errors
- `map_candidates_to_schema` — given candidates and schema fields, returns correct FieldCandidateMap
- `check_inconsistencies` — given FieldCandidateMap, returns correct InconsistencyReport
- `SchemaLifecycleStatus` transitions

**No I/O**: Unit tests use only in-memory Python objects. No database, no HTTP, no PDF generation.

**Location**: `tests/domain/`

---

### Layer 2 — Integration Tests

**Scope**: Full pipeline from PDF bytes to ValidationReport.

**What is tested**:
- `ValidationPipelineService.run()` end-to-end with fixture PDFs
- Correct status (PASS/FAIL/AMBIGUOUS) for each fixture
- Evidence fields are populated correctly
- Noisy documents produce the same result as clean counterparts
- Determinism (same PDF → same result, N times)

**Location**: `tests/domain/validation/test_pipeline_wine_pdf.py`, `test_pipeline_wine_csv_fixtures.py`

---

### Layer 3 — API Tests

**Scope**: HTTP endpoint behavior.

**What is tested**:
- Correct HTTP status codes for all error conditions
- Correct response body schema for PASS/FAIL/AMBIGUOUS
- Schema management endpoints (create, archive, list)
- Authentication/authorization at the project level (project exists check)

**Tools**: `pytest` + `httpx.AsyncClient` with test database

**Location**: `tests/api/`

---

### Layer 4 — Regression Tests

**Scope**: Fixed inputs with fixed expected outputs.

**Definition**: A regression test is a test case where the expected output is pre-determined and cannot change without explicit human approval. Any test that changes its expected output after a code change is a regression.

**These tests must never auto-update their expected outputs.** If they fail, it must be investigated.

**Location**: `tests/domain/validation/test_pipeline_wine_csv_fixtures.py` (parametrized over corpus)

---

## 4. Test Configuration

```python
# tests/conftest.py

@pytest.fixture
def wine_schema_body():
    return json.loads(
        Path("tests/fixtures/wine/schema.json").read_text()
    )

@pytest.fixture
def llm_disabled_settings(monkeypatch):
    monkeypatch.setenv("VALIDATION_LLM_FALLBACK_ENABLED", "false")
```

All tests run with LLM disabled by default. LLM tests are marked `@pytest.mark.llm` and excluded from the default test run.

---

## 5. Running Tests

```bash
cd backend

# All tests (fast, no LLM)
pytest tests/

# Unit tests only
pytest tests/domain/

# API tests only
pytest tests/api/

# LLM-involved tests (slow, requires Ollama running)
pytest tests/ -m llm

# With coverage
pytest tests/ --cov=ocean_read --cov-report=html
```

---

## 6. Success Criteria

The test strategy is successful if:

- All PASS/FAIL/AMBIGUOUS scenarios are covered by at least one test case
- `pytest tests/` completes without failures on a clean checkout
- No manual review is required to determine correctness
- A code change that affects validation output causes at least one test to fail
- Coverage on domain layer is ≥ 90%

---

## 7. Failure Criteria

A test run is considered failed if any of the following occur:

- Any test assertion fails
- Any test produces a non-deterministic result (flaky)
- Evidence is missing from a non-required FAIL error
- The pipeline produces a different status on the same input twice

---

## Cross-References

| Topic | Document |
|-------|----------|
| Test case catalog | `04_TESTING/TEST_CASES.md` |
| Dataset and fixtures | `04_TESTING/DATASET_STRATEGY.md` |
| Generator spec | `04_TESTING/TEST_GENERATOR_SPEC.md` |
| Wine corpus pipeline | `04_TESTING/WINE_DATASET_PIPELINE.md` |
