# Pipeline Implementation — Code Design Per Stage

## Overview

This document maps each pipeline stage to its code location, describes the implementation design, and defines the refactoring required to move from the Milestone 1 (wine-specific) implementation to the target (schema-driven, generic) implementation.

Read `01_ARCHITECTURE/PIPELINE_DESIGN.md` for the stage specifications. This document is about the code.

---

## Current State vs. Target State

| Aspect | Current (Milestone 1) | Target (Post-Refactor) |
|--------|----------------------|----------------------|
| Field names | Hardcoded (`ph`, `alcohol`, `quality`) | Driven by schema body |
| Extractors | `extractors_wine.py` (wine-specific) | `extractors.py` (generic `SchemaAwareExtractor`) |
| Pipeline function | `run_wine_pdf_validation()` | `ValidationPipelineService.run()` |
| Schema mapping | None (candidates assumed to match fields) | Explicit `schema_mapping()` function |
| Inconsistency check | None | `inconsistency_check()` function |
| Gap-fill pass | None | `gap_fill_pass()` function |
| AMBIGUOUS status | Not supported | Supported via `InconsistencyReport` |
| Run persistence | Not implemented | `ValidationRunRepository.save()` |

---

## Stage 1 — Block Extraction

**File**: `ocean_read/domain/validation/pdf_blocks.py`

**Functions**:
- `parse_pdf_blocks(data: bytes) -> list[TextBlock]`
- `infer_section_labels(blocks: list[TextBlock]) -> list[TextBlock]`

**Implementation notes**:

`infer_section_labels` is a post-processing step that must be added to the current implementation. It scans for "heading-like" blocks and propagates the heading text as `section_label` to all subsequent blocks until the next heading is encountered.

**Heading detection heuristic**:
- Block text is short (< 80 chars)
- Block text does not contain colons (not a label-value pair)
- Font size is larger than surrounding blocks (requires `page.get_text("dict")` span data)
- OR: all-caps text
- OR: ends without punctuation

This is a best-effort heuristic. It does not need to be perfect — section labels are hints, not guarantees.

**Tests**: `tests/domain/validation/test_pdf_blocks.py`

---

## Stage 2 — Discovery Pass (Extraction)

**Current file**: `ocean_read/domain/validation/extractors_wine.py`
**Target file**: `ocean_read/domain/validation/extractors.py`

**Current functions** (wine-specific, to be deprecated):
- `extract_regex_wine(blocks) -> list[ExtractionCandidate]`
- `extract_layout_wine(blocks) -> list[ExtractionCandidate]`
- `ensemble_wine_extractors(blocks) -> list[ExtractionCandidate]`

**Target class**:

```python
class SchemaAwareExtractor:
    """Generic extractor driven by schema field definitions."""

    def __init__(self, schema_body: dict):
        self._fields = schema_body.get("fields", {})
        self._compiled = self._compile_patterns()

    def _compile_patterns(self) -> dict[str, list[re.Pattern]]:
        """Pre-compile regex patterns for each field from aliases + regex_hint."""
        patterns = {}
        for field_name, spec in self._fields.items():
            field_patterns = []
            aliases = [field_name] + list(spec.get("aliases") or [])
            # Build default label-colon pattern from each alias
            for alias in aliases:
                escaped = re.escape(alias)
                field_patterns.append(
                    re.compile(rf"(?i){escaped}\s*[:=]\s*([\d.]+)\s*%?")
                )
            # Add custom regex_hint if declared
            if hint := spec.get("regex_hint"):
                field_patterns.append(re.compile(hint))
            patterns[field_name] = field_patterns
        return patterns

    def extract_regex(self, blocks: list[TextBlock]) -> list[ExtractionCandidate]:
        """Run all compiled regex patterns against all blocks."""
        ...

    def extract_layout(self, blocks: list[TextBlock]) -> list[ExtractionCandidate]:
        """Spatial heuristics: label + value in proximity."""
        ...

    def run_discovery(self, blocks: list[TextBlock]) -> list[ExtractionCandidate]:
        """Run all extractors, return combined candidate list."""
        return self.extract_regex(blocks) + self.extract_layout(blocks)
```

**Migration path**:
1. Write `SchemaAwareExtractor` in `extractors.py` with tests.
2. Wire it into `validation_pipeline.py` alongside `extractors_wine.py` (both coexist during transition).
3. Once tests confirm equal or better accuracy, remove `extractors_wine.py`.
4. The wine schema DSL includes field definitions with aliases that reproduce the current hardcoded behavior.

---

## Stage 3 — Schema Mapping

**File**: `ocean_read/domain/validation/mapping.py` (new file)

**Function**:

```python
def map_candidates_to_schema(
    candidates: list[ExtractionCandidate],
    schema_fields: dict[str, dict],
) -> FieldCandidateMap:
    """
    Group candidates by schema field name.

    Returns a FieldCandidateMap with status:
    - "found"     — 1 candidate, or 2+ with identical values
    - "missing"   — 0 candidates
    - "ambiguous" — 2+ candidates with distinct values
    """
    ...
```

**Normalization**: Field name matching uses a normalizer:
```python
def normalize_field_name(name: str) -> str:
    return name.lower().replace(" ", "_").replace("-", "_").strip()
```

A candidate with `field="Alcohol %"` maps to schema field `"alcohol"` if `normalize("Alcohol %") == normalize("alcohol")` or if `"Alcohol %"` appears in the field's `aliases`.

---

## Stage 4 — Gap-Fill Pass

**File**: `ocean_read/domain/validation/mapping.py`

**Function**:

```python
async def gap_fill_pass(
    blocks: list[TextBlock],
    missing_fields: list[str],
    schema_body: dict,
    *,
    llm_client: OllamaLLMClient | None = None,
) -> list[ExtractionCandidate]:
    """
    Targeted second-pass for fields not found in discovery.
    Tries synonym regex → section-scoped layout → LLM (if enabled).
    """
    ...
```

**LLM gap-fill prompt** (fixed, versioned):
```
System: Extract the value of field "{field_name}" from the document text below.
        Respond with JSON only: {"{field_name}": <number|string|null>}.
        Use null if not found. No prose.

User: [document text]
```

---

## Stage 5 — Inconsistency Check

**File**: `ocean_read/domain/validation/mapping.py`

**Function**:

```python
def check_inconsistencies(
    field_candidate_map: FieldCandidateMap,
) -> InconsistencyReport:
    """
    Identify fields with ambiguous status and return a report.
    """
    ambiguous = [
        AmbiguousFieldEntry(
            field=field,
            count=len(entry.candidates),
            candidates=entry.candidates,
        )
        for field, entry in field_candidate_map.items()
        if entry.status == "ambiguous"
    ]
    return InconsistencyReport(
        has_ambiguity=bool(ambiguous),
        ambiguous_fields=ambiguous,
    )
```

---

## Stage 6 — Resolution

**File**: `ocean_read/domain/validation/resolution.py`

**Current functions** (keep as-is, they are correct):
- `resolve_field_candidate(field, candidates) -> ExtractionCandidate`
- `resolve_document_with_evidence(candidates) -> tuple[ResolvedDocument, EvidenceMap]`

**Change required**: The current `resolve_document_with_evidence` takes a flat `list[ExtractionCandidate]`. It needs to accept a `FieldCandidateMap` instead, operating only on `found` fields.

```python
def resolve_from_map(
    field_candidate_map: FieldCandidateMap,
) -> tuple[dict[str, Any], dict[str, dict]]:
    """Resolve all 'found' fields. Skip 'missing' and 'ambiguous'."""
    ...
```

---

## Stage 7 — Validation Engine

**File**: `ocean_read/domain/validation/engine.py`

**Functions**:
- `validate_schema(resolved, schema_body, ...) -> ValidationReport` (PASS/FAIL only; alias `validate_wine_style_schema`)

**Orchestration** (full pipeline / `AMBIGUOUS`): `ocean_read/services/validation_pipeline.py` — `run_wine_pdf_validation(...) -> PipelineValidationResult` (`PASS` | `FAIL` | `AMBIGUOUS`).

**Target function**:
- `validate(resolved_document, schema_body, evidence_map, ...) -> ValidationReport`

**Refactor**:
Replace the current inline rule logic with a `RuleRegistry` dispatch:

```python
def validate(
    resolved: dict[str, Any],
    schema_body: dict,
    evidence_map: dict[str, dict] | None = None,
    schema_key: str | None = None,
    version_label: str | None = None,
) -> ValidationReport:
    errors: list[FieldValidationError] = []
    ev = evidence_map or {}
    rules = schema_body.get("rules") or []
    fields_spec = schema_body.get("fields") or {}

    for rule_id in rules:
        evaluator = RuleRegistry.get(rule_id)
        for field_name, spec in fields_spec.items():
            value = resolved.get(field_name)
            error = evaluator.evaluate(field_name, value, spec, ev.get(field_name))
            if error:
                errors.append(error)

    status = "PASS" if not errors else "FAIL"
    return ValidationReport(
        schema_key=schema_key,
        schema_version=version_label,
        status=status,
        errors=tuple(errors),
    )
```

---

## Pipeline Orchestration

**File**: `ocean_read/services/validation_pipeline.py`

**Current function** (wine-specific):
```python
async def run_wine_pdf_validation(pdf_bytes, schema_body, schema_key, version_label) -> ValidationReport
```

**Target class**:

```python
class ValidationPipelineService:
    """
    Orchestrates all pipeline stages.
    This is the single entry point for document validation.
    """

    def __init__(
        self,
        *,
        llm_enabled: bool = False,
        llm_client: OllamaLLMClient | None = None,
        run_repository: ValidationRunRepository | None = None,
    ):
        self._llm_enabled = llm_enabled
        self._llm_client = llm_client
        self._run_repo = run_repository

    async def run(
        self,
        pdf_bytes: bytes,
        *,
        schema_body: dict,
        schema_key: str,
        version_label: str,
        project_id: str | None = None,
    ) -> ValidationReport:
        # Stage 1: Block Extraction
        blocks = parse_pdf_blocks(pdf_bytes)
        blocks = infer_section_labels(blocks)

        # Stage 2: Discovery Pass
        extractor = SchemaAwareExtractor(schema_body)
        candidates = extractor.run_discovery(blocks)

        # Stage 3: Schema Mapping
        field_map = map_candidates_to_schema(candidates, schema_body["fields"])

        # Stage 4: Gap-Fill
        missing = [f for f, e in field_map.items() if e.status == "missing"]
        if missing:
            gap_candidates = await gap_fill_pass(
                blocks, missing, schema_body,
                llm_client=self._llm_client if self._llm_enabled else None,
            )
            field_map = merge_gap_fill(field_map, gap_candidates, schema_body["fields"])

        # Stage 5: Inconsistency Check
        inconsistency_report = check_inconsistencies(field_map)

        # Stage 6: Resolution
        resolved, evidence_map = resolve_from_map(field_map)

        # Stage 7: Validation
        errors = validate(resolved, schema_body, evidence_map)

        # Stage 8: Assemble Report
        status = "AMBIGUOUS" if inconsistency_report.has_ambiguity else ("FAIL" if errors else "PASS")
        report = ValidationReport(
            status=status,
            schema_key=schema_key,
            schema_version=version_label,
            errors=tuple(errors),
            ambiguous_fields=tuple(inconsistency_report.ambiguous_fields),
        )

        # Persist run snapshot (M2)
        if self._run_repo and project_id:
            await self._save_run(project_id, schema_key, version_label, pdf_bytes, blocks, candidates, field_map, resolved, report)

        return report
```

---

## LLM Integration

**File**: `ocean_read/services/validation_llm.py`

The LLM service is called by the pipeline only when:
1. `validation_llm_fallback_enabled = true` in settings.
2. At least one field has `status = "missing"` after the discovery pass.

The LLM is never called for validation — only for extraction.

**Ollama client**: `ocean_read/providers/ollama.py`
- `OllamaLLMClient.complete(system, user, temperature=0.0) -> str`
- `loads_json_maybe_with_fence(raw: str) -> Any` — strips markdown fences from LLM output

---

## Testing

Each stage has its own test file:

| Stage | Test file |
|-------|-----------|
| Block extraction | `tests/domain/validation/test_pdf_blocks.py` |
| Extractors | `tests/domain/validation/test_extractors_wine.py` (current) → `test_extractors.py` (target) |
| Schema mapping + inconsistency | `tests/domain/validation/test_mapping.py` (new) |
| Resolution | `tests/domain/validation/test_resolution.py` |
| Validation engine | `tests/domain/validation/test_engine_wine.py` (current) → `test_engine.py` (target) |
| Full pipeline | `tests/domain/validation/test_pipeline_wine_pdf.py` |
| API | `tests/api/test_validation_api.py` |

---

## Cross-References

| Topic | Document |
|-------|----------|
| Stage algorithms | `01_ARCHITECTURE/PIPELINE_DESIGN.md` |
| Domain types | `03_DOMAIN/DOMAIN_MODEL.md` |
| Extraction model | `03_DOMAIN/EXTRACTION_MODEL.md` |
| Resolution model | `03_DOMAIN/RESOLUTION_MODEL.md` |
| Rule engine | `03_DOMAIN/RULE_ENGINE.md` |
| API contracts | `05_IMPLEMENTATION/API_SPEC.md` |
