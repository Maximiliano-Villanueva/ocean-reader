# Pipeline Design — Stage-by-Stage Specification

## Overview

The validation pipeline is a linear, stateless transformation chain. Each stage receives a well-typed input and produces a well-typed output. No stage has side effects (except the final run-persistence step). Stages can be tested and reasoned about in isolation.

```
PDF bytes → Blocks → Candidates → MappedCandidates → ResolvedDocument → ValidationReport
```

---

## Stage 1 — Block Extraction

**Purpose**: Convert raw PDF bytes into a stable list of text blocks with geometry and section context.

**Input**: `bytes` (raw PDF content)

**Output**: `list[TextBlock]`

```
TextBlock {
  id:           str          # stable "b0", "b1", ... (document order)
  page:         int          # 1-indexed
  bbox:         (x0,y0,x1,y1)  # points on the page coordinate system
  text:         str          # concatenated span text, stripped
  section_label: str | None  # inferred section heading (e.g. "Chemical Analysis")
}
```

**Algorithm**:
1. Open PDF with PyMuPDF (`fitz.open`).
2. For each page, call `page.get_text("dict")` to get the layout tree.
3. Walk blocks of `type=0` (text blocks). Skip images and drawings.
4. Concatenate span texts within each block into a single string.
5. Assign stable IDs in document order (`b0`, `b1`, ...).
6. Infer `section_label` by scanning heading-like blocks (large font, bold, short text) preceding each block.

**Constraints**:
- IDs are assigned once and never change for a given PDF. Tests depend on stable IDs.
- Empty blocks (whitespace-only) are discarded.
- `bbox` values are raw PyMuPDF floats (page-coordinate points).

---

## Stage 2 — Discovery Pass

**Purpose**: Extract every recognizable entity from every section of the document — without knowing what the schema needs. Produces a rich candidate pool.

**Input**: `list[TextBlock]`

**Output**: `list[ExtractionCandidate]`

```
ExtractionCandidate {
  field:          str          # tentative field name (e.g. "alcohol", "temperature_1")
  value:          Any          # extracted value (float, str, date, etc.)
  source:         str          # "regex" | "layout" | "llm"
  confidence:     float        # 0.0 – 1.0
  block_id:       str          # reference to source TextBlock.id
  page:           int
  evidence_text:  str          # the text span that produced this candidate
  bbox:           (x0,y0,x1,y1) | None
  section_label:  str | None   # inherited from block
}
```

**Extraction techniques (applied in order, all results kept)**:

1. **Regex extraction** — anchored key-value patterns (`Label: Value`, `Label = Value`). Highest confidence (0.90–0.98).
2. **Layout heuristics** — spatial proximity patterns (label in left column, value in right column; label on line N, value on line N+1). Medium confidence (0.50–0.75).
3. **LLM extraction** (optional, controlled) — only triggered if `validation_llm_fallback_enabled = true` in settings. Temperature 0, structured JSON output. Lowest confidence (0.35–0.45).

**Key principle**: Discovery is exhaustive. All extractors run on all blocks. The result is a superset of what the schema needs. Downstream stages select and filter.

---

## Stage 3 — Schema Mapping

**Purpose**: Match discovered candidates to the fields declared in the validation schema. Produces a per-field view: how many candidates were found for each required field.

**Input**: `list[ExtractionCandidate]`, `SchemaBody`

**Output**: `FieldCandidateMap`

```
FieldCandidateMap {
  field_name → {
    "candidates": list[ExtractionCandidate],
    "status":     "found" | "missing" | "ambiguous"
  }
}
```

**Mapping logic**:
- A candidate maps to a schema field if `candidate.field` matches the field name (exact or normalized, e.g. case-insensitive, underscore-space equivalence).
- If 0 candidates → `status = "missing"` → triggers Gap-Fill Pass.
- If 1 candidate → `status = "found"`.
- If 2+ candidates with **different** values → `status = "ambiguous"` → surfaces all to human.
- If 2+ candidates with **identical** values → treated as 1 (duplicate evidence is fine, collapsed to one).

**Extra candidates** (discovered but not in schema) are preserved in the run snapshot as `discovered_extras`. They are not validated but are available for auditing and future schema expansion.

---

## Stage 4 — Gap-Fill Pass

**Purpose**: For every field with `status = "missing"` after discovery, make a targeted second attempt to find a value.

**Input**: `list[TextBlock]`, `list[str]` (missing field names), `SchemaBody`

**Output**: `list[ExtractionCandidate]` (additional candidates, merged into FieldCandidateMap)

**Gap-fill techniques (tried in order, first success wins per field)**:

1. **Synonym regex** — the schema can declare `aliases` for a field (e.g. `"alc."`, `"Alcohol %"`). These are tried as additional regex patterns.
2. **Section-scoped layout scan** — if the schema declares a `section_hint` for a field, re-scan only blocks within that section with relaxed heuristics.
3. **LLM targeted extraction** — ask the LLM specifically: "Find the value of `{field_name}` in this text." Temperature 0, structured output. Lowest priority.

**Constraint**: gap-fill results are labeled `source="layout"` or `source="llm"` per technique used. They receive lower confidence than discovery-pass results.

---

## Stage 5 — Inconsistency Check

**Purpose**: Identify fields where multiple conflicting values exist. These cannot be silently resolved — they must be surfaced.

**Input**: `FieldCandidateMap`

**Output**: `InconsistencyReport`

```
InconsistencyReport {
  ambiguous_fields: list[{
    field:       str,
    candidates:  list[ExtractionCandidate],  # all conflicting candidates
    count:       int
  }]
  has_ambiguity: bool
}
```

**Definition of inconsistency**: Two candidates for the same field where `abs(val_a - val_b) > epsilon` (for numeric fields) or `val_a != val_b` (for string/date fields).

**Effect on validation result**:
- If `has_ambiguity = true`, the final `ValidationReport.status` is `AMBIGUOUS`.
- All candidates for ambiguous fields are included in the report with full evidence.
- AMBIGUOUS is not a PASS. It signals that a human must review the specific fields before the document can be considered validated.

---

## Stage 6 — Resolution

**Purpose**: For non-ambiguous fields, deterministically select exactly one value per field.

**Input**: `FieldCandidateMap` (fields with `status = "found"`)

**Output**: `ResolvedDocument`

```
ResolvedDocument {
  field_name → {
    "value":    Any,
    "evidence": EvidenceRef
  }
}

EvidenceRef {
  text:     str,
  block_id: str,
  page:     int,
  bbox:     (x0,y0,x1,y1) | None
}
```

**Resolution priority** (highest wins):

| Priority | Source | Rationale |
|----------|--------|-----------|
| 1 (highest) | `regex` | Anchored patterns, least ambiguous |
| 2 | `layout` | Spatial heuristics, reliable in templated docs |
| 3 (lowest) | `llm` | Probabilistic, last resort |

**Tie-breaking within same priority** (in order):
1. Highest `confidence` value
2. First occurrence in document order (`block_id` lexicographic)

Resolution is fully reproducible: same candidates → same winner. No randomness.

---

## Stage 7 — Validation Engine

**Purpose**: Apply schema rules to resolved values. Produces a list of rule violations.

**Input**: `ResolvedDocument`, `SchemaBody`

**Output**: `list[ValidationError]`

```
ValidationError {
  field:    str,
  value:    Any,
  expected: Any,
  rule:     str,      # rule identifier
  evidence: EvidenceRef | None
}
```

**Supported rules (Milestone 1)**:

| Rule | Description |
|------|-------------|
| `required` | Field must be present in ResolvedDocument |
| `range_validation` | Numeric value must satisfy `min ≤ value ≤ max` |
| `type_check` | Value must be coercible to declared type (`number`, `string`, `date`) |

**Supported rules (Milestone 3 — future)**:

| Rule | Description |
|------|-------------|
| `cross_field` | Expression involving 2+ fields must evaluate to true |
| `repeating_group` | Template rule applied to each row of a detected table/list section |
| `reference_lookup` | Value must exist in a declared reference dataset |

**Engine contract**: The validation engine is a pure function. Same `ResolvedDocument` + same `SchemaBody` = same `list[ValidationError]`. No I/O.

---

## Stage 8 — Result Assembly

**Purpose**: Combine all pipeline outputs into a single `ValidationReport` and determine final status.

**Input**: `list[ValidationError]`, `InconsistencyReport`, `SchemaBody`, schema metadata

**Output**: `ValidationReport`

```
ValidationReport {
  status:         "PASS" | "FAIL" | "AMBIGUOUS",
  schema_id:      str,
  schema_version: str,
  errors:         list[ValidationError],
  ambiguous:      list[AmbiguousField],   # from InconsistencyReport
  extras:         list[ExtractionCandidate]  # discovered but not in schema
}
```

**Status determination**:
- `AMBIGUOUS` — if `InconsistencyReport.has_ambiguity = true` (takes precedence)
- `FAIL` — if `errors` is non-empty and no ambiguity
- `PASS` — if `errors` is empty and no ambiguity

---

## Pipeline Orchestration

The pipeline is orchestrated by `ValidationPipelineService` in the application layer. It:

1. Accepts raw bytes + schema body + schema metadata.
2. Calls each stage function in order.
3. Assembles the final report.
4. Persists a `ValidationRun` snapshot (M2+).
5. Returns the report to the HTTP layer.

The service is the only place that wires stages together. Each stage is independently testable with unit tests.

---

## Cross-References

| Topic | Document |
|-------|----------|
| Data shapes in detail | `01_ARCHITECTURE/DATA_FLOW.md` |
| ExtractionCandidate domain model | `03_DOMAIN/EXTRACTION_MODEL.md` |
| Resolution algorithm detail | `03_DOMAIN/RESOLUTION_MODEL.md` |
| Rule engine detail | `03_DOMAIN/RULE_ENGINE.md` |
| Pipeline code structure | `05_IMPLEMENTATION/PIPELINE_IMPLEMENTATION.md` |
