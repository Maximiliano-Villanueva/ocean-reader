# Test Cases — Complete Catalog

## Test Case Naming Convention

`TC-{LAYER}-{NUMBER}: {description}`

Layers: `UNIT`, `INTG` (integration), `API`, `E2E`

---

## Block Extraction (Unit)

### TC-UNIT-001: Basic block extraction
- **Input**: Simple PDF with 3 text blocks
- **Expected**: 3 `TextBlock` objects with correct ids, pages, text, bbox
- **File**: `test_pdf_blocks.py`

### TC-UNIT-002: Multi-page extraction
- **Input**: 2-page PDF
- **Expected**: Blocks from page 1 and 2; IDs are globally sequential (`b0`...`bN`)

### TC-UNIT-003: Empty block filtering
- **Input**: PDF with whitespace-only blocks
- **Expected**: Whitespace blocks are not included in output

### TC-UNIT-004: Section label inference
- **Input**: PDF with a heading block followed by content blocks
- **Expected**: Content blocks have `section_label` set to heading text; heading block has `section_label=None`

### TC-UNIT-005: Image blocks are skipped
- **Input**: PDF with an image block (type != 0) between text blocks
- **Expected**: Image block is not in output; IDs remain sequential

---

## Extraction — Regex (Unit)

### TC-UNIT-010: Standard regex match
- **Input**: Block with text `"pH: 3.42"`
- **Expected**: Candidate `{field="ph", value=3.42, source="regex", confidence=0.95}`

### TC-UNIT-011: Alias match
- **Input**: Block with text `"EtOH: 11.2%"`; schema declares alias `"EtOH"` for `alcohol`
- **Expected**: Candidate `{field="alcohol", value=11.2, source="regex"}`

### TC-UNIT-012: No false positive from unrelated number
- **Input**: Block with text `"Equipment ID: 42"` (no field label)
- **Expected**: No candidates produced for any schema field

### TC-UNIT-013: Multiple fields in one block
- **Input**: Block with `"pH: 3.4, Alcohol: 11.2%"`
- **Expected**: Two candidates, one for `ph` and one for `alcohol`

### TC-UNIT-014: Value with spaces and unit
- **Input**: Block with `"Alcohol content  =  11.2 %"`
- **Expected**: Candidate `{field="alcohol", value=11.2}`

---

## Extraction — Layout (Unit)

### TC-UNIT-020: Label and value on same line, no colon
- **Input**: Block with line `"Alcohol    11.2"`
- **Expected**: Layout candidate for `alcohol`, lower confidence than regex

### TC-UNIT-021: Label and value on adjacent lines
- **Input**: Two-line block: `"Quality\n6"`
- **Expected**: Layout candidate for `quality`

---

## Schema Mapping (Unit)

### TC-UNIT-030: All fields found
- **Input**: Candidates covering all schema fields, each with one value
- **Expected**: All entries in `FieldCandidateMap` have `status="found"`

### TC-UNIT-031: Field missing
- **Input**: No candidate for `volatile_acidity`
- **Expected**: `FieldCandidateMap["volatile_acidity"].status == "missing"`

### TC-UNIT-032: Field ambiguous (two different values)
- **Input**: Two candidates for `temperature`: 18.5 and 22.0
- **Expected**: `FieldCandidateMap["temperature"].status == "ambiguous"`, both candidates present

### TC-UNIT-033: Field found with duplicate evidence (same value, different blocks)
- **Input**: Two candidates for `ph`, both with value 3.42, from different blocks
- **Expected**: `FieldCandidateMap["ph"].status == "found"` (not ambiguous)

### TC-UNIT-034: Extra field (in candidates, not in schema)
- **Input**: Candidate for field `density` which is not in the schema
- **Expected**: `density` not in `FieldCandidateMap`; candidate preserved in extras

---

## Resolution (Unit)

### TC-UNIT-040: Regex wins over layout
- **Input**: Two candidates for `alcohol`: `{source="regex", confidence=0.95}` and `{source="layout", confidence=0.75}`
- **Expected**: Regex candidate selected

### TC-UNIT-041: Confidence tie-breaking within same source
- **Input**: Two regex candidates for `ph`: confidences 0.95 and 0.90
- **Expected**: Confidence 0.95 wins

### TC-UNIT-042: Block order tie-breaking
- **Input**: Two identical candidates (same source, same confidence), from `b3` and `b12`
- **Expected**: `b3` wins (first in document order)

### TC-UNIT-043: No candidates raises error
- **Input**: Empty candidates list
- **Expected**: `ValueError` raised

### TC-UNIT-044: Evidence carried to resolved document
- **Input**: Winning candidate has `evidence_text="Alcohol: 11.2%"`, `block_id="b3"`, `page=1`, `bbox=[...]`
- **Expected**: `ResolvedDocument["alcohol"].evidence` has all four fields

---

## Validation Engine (Unit)

### TC-UNIT-050: PASS — all fields within range
- **Input**: `{ph: 3.42, alcohol: 11.2, quality: 6}`, schema with range [8,15] for alcohol
- **Expected**: `ValidationReport.status == "PASS"`, no errors

### TC-UNIT-051: FAIL — range violation
- **Input**: `{alcohol: 18.0}`, schema with range [8.0, 15.0]
- **Expected**: `ValidationError(field="alcohol", value=18.0, expected=[8.0,15.0], rule="range_validation")`

### TC-UNIT-052: FAIL — missing required field
- **Input**: Resolved document missing `ph`; schema has `required: true` for `ph`
- **Expected**: `ValidationError(field="ph", value=None, expected="present", rule="required")`

### TC-UNIT-053: PASS — value exactly at boundary
- **Input**: `{alcohol: 8.0}`, schema range [8.0, 15.0]
- **Expected**: PASS (boundaries are inclusive)

### TC-UNIT-054: FAIL — value just outside boundary
- **Input**: `{alcohol: 7.99}`, schema range [8.0, 15.0]
- **Expected**: FAIL

### TC-UNIT-055: Multiple errors collected
- **Input**: Two fields out of range
- **Expected**: Both errors in `report.errors` (no short-circuit)

### TC-UNIT-056: Non-numeric value for number field
- **Input**: `{ph: "high"}`, schema declares `type: number`
- **Expected**: FAIL with `type_check` rule

---

## Integration — Full Pipeline (INTG)

### TC-INTG-001: Clean wine document → PASS
- **Input**: Clean PDF fixture, all values within range
- **Expected**: `status == "PASS"`, 0 errors

### TC-INTG-002: Clean wine document → FAIL (alcohol out of range)
- **Input**: Clean PDF fixture, `alcohol = 18.0`
- **Expected**: `status == "FAIL"`, 1 error on `alcohol`, `rule = "range_validation"`

### TC-INTG-003: Clean wine document → FAIL (missing field)
- **Input**: Clean PDF fixture where `quality` field is absent from the document
- **Expected**: `status == "FAIL"`, 1 error on `quality`, `rule = "required"`

### TC-INTG-004: Noisy wine document → same result as clean variant
- **Input**: Noisy variant of a known-PASS row
- **Expected**: `status == "PASS"`, same evidence fields as clean variant

### TC-INTG-005: AMBIGUOUS — document with two temperature values
- **Input**: PDF with "Fermentation temp: 18.5°C" and "Bottling temp: 22.0°C"; schema field `temperature`
- **Expected**: `status == "AMBIGUOUS"`, 2 candidates for `temperature` with evidence

### TC-INTG-006: Pipeline determinism
- **Input**: Same PDF submitted 3 times
- **Expected**: All three results identical (status, errors, block_ids, evidence text)

### TC-INTG-007: Evidence fields are valid
- **Input**: Any FAIL document
- **Expected**: Every `ValidationError.evidence` has non-empty `text`, valid `block_id`, `page >= 1`

### TC-INTG-008: LLM disabled produces same result as LLM enabled when regex is sufficient
- **Input**: Well-structured PDF; run once with LLM disabled, once with LLM enabled
- **Expected**: Identical results (regex should find everything; LLM result should be overridden by resolution priority)

---

## API Tests (API)

### TC-API-001: POST /validate-document — PASS
- **Input**: Valid multipart request with clean wine PDF
- **Expected**: `200`, `{status: "PASS", results: []}`

### TC-API-002: POST /validate-document — FAIL
- **Input**: Wine PDF with alcohol out of range
- **Expected**: `200`, `{status: "FAIL", results: [{field: "alcohol", rule: "range_validation"}]}`

### TC-API-003: POST /validate-document — schema not found
- **Input**: Unknown `schema_id`
- **Expected**: `404`

### TC-API-004: POST /validate-document — schema not active
- **Input**: `schema_id` pointing to archived version
- **Expected**: `409`

### TC-API-005: POST /validate-document — file too large
- **Input**: PDF > 30MB
- **Expected**: `413`

### TC-API-006: POST /validate-document — wrong file type
- **Input**: A `.txt` file
- **Expected**: `400`

### TC-API-007: POST /validate-document — missing required form fields
- **Input**: Multipart without `schema_id`
- **Expected**: `422`

### TC-API-008: GET /projects/:id/validation-schemas — grouped response
- **Input**: Project with 2 schema keys, 3 total versions
- **Expected**: `200`, response grouped by key with versions array

---

## Regression Catalog

The following tests must never fail after their initial pass. Any change to the pipeline that causes these to fail is a breaking change and requires an ADR.

| Test ID | Description | Failure action |
|---------|-------------|----------------|
| TC-INTG-001 | PASS accuracy on clean corpus | ADR required |
| TC-INTG-004 | Noisy == clean result | Extractor review |
| TC-INTG-006 | Pipeline determinism | Block — determinism is non-negotiable |
| TC-API-001 | API returns correct PASS | Breaking change |
| TC-API-002 | API returns correct FAIL with evidence | Breaking change |

---

## Cross-References

| Topic | Document |
|-------|----------|
| Test strategy | `04_TESTING/TEST_STRATEGY.md` |
| Dataset and fixtures | `04_TESTING/DATASET_STRATEGY.md` |
| Wine pipeline | `04_TESTING/WINE_DATASET_PIPELINE.md` |
