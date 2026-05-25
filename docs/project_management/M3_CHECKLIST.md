# M3 — Advanced validation rules checklist

End state: **cross-field** and **repeating group** rules on `"version": "2"` schemas, sandboxed expressions, schema DSL validation, pipeline + corpus coverage.

Canonical spec: [`MILESTONE_3_ADVANCED_RULES.md`](../document_validation_docs/02_MILESTONES/MILESTONE_3_ADVANCED_RULES.md).

## Domain & engine

- [x] `expression_evaluator.py` — recursive-descent AST; **no** `eval` / `exec`
- [x] Cross-field rules in `validate_schema` when `version: "2"`; skip when referenced values missing
- [x] Error message `{field}` interpolation; evidence `by_field` for involved fields
- [x] `repeating_groups.py` — **table** (bbox gaps + pipe), **list** (tokens per line), **sections** (paragraphs)
- [x] Section body blocks after layout header line (`_blocks_for_section` / `_section_text_blob`)
- [x] Row errors `group[row_index]`; `group_not_found` when section empty
- [x] `schema_dsl.collect_schema_dsl_errors` — publish **400** on invalid M3 schema

## API & assist

- [x] `POST …/suggest-cross-field-rule` when `VALIDATION_SCHEMA_LLM_ASSIST_ENABLED=true`
- [x] `schema_expression_assist.py` — LLM output re-validated against allow-list

## Pipeline

- [x] `run_wine_pdf_validation` → `validate_schema(..., blocks=group_blocks)` after resolution
- [x] Early **AMBIGUOUS** exit still skips cross-field / groups (by design)

## Tests (pytest)

| Area | Module |
|------|--------|
| Expression language | `test_expression_evaluator.py` |
| Engine + cross-field table | `test_engine_m3.py` |
| Group extraction | `test_repeating_groups_extract.py`, `test_pdf_span_blocks.py` |
| DSL | `test_schema_dsl.py` |
| Pipeline cross-field + groups | `test_validation_pipeline_m3.py` |
| M3 corpus PDFs | `test_pipeline_m3_corpus.py` |
| LLM assist | `test_schema_expression_assist.py`, `test_validation_api.py` (suggest) |

Run M3-focused suite from `backend/`:

```bash
.venv/bin/pytest tests/domain/validation/test_engine_m3.py \
  tests/domain/validation/test_expression_evaluator.py \
  tests/domain/validation/test_repeating_groups_extract.py \
  tests/domain/validation/test_schema_dsl.py \
  tests/services/test_validation_pipeline_m3.py \
  tests/services/test_pipeline_m3_corpus.py -q
```

## Fixtures

- [x] `tests/fixtures/wine/schema_m3_wine_cross_field.json`
- [x] `tests/fixtures/wine/m3_corpus_index.json` + `m3_cross_field/syn_m3_cf_*.pdf`
- [x] Regenerate M3 PDFs: `python backend/tests/fixtures/wine/generate_fixtures.py --m3-only`

## Frontend (functional, not full wireframe)

- [x] `ProjectSchemasPage` — cross-field + repeating-group **append forms**, JSON editor, LLM suggest
- [x] PDF evidence viewer with bbox highlights; ambiguous fields dashed, others green
- [ ] Card-based rule editor (When/Then, per-rule Edit/Delete) per M3 Part 4 wireframe — **deferred**

## Known gaps / follow-ups

- [ ] SO₂ cross-field on **real** wine PDFs (fields exist in M3 schema; corpus PDFs are ph/alcohol/quality only)
- [ ] `structure_hint: list` uses **whitespace tokens per line**; use `sections` for `Label: value` paragraphs (documented in `repeating_groups.py`)
- [ ] Docker E2E script still uses M1 `wine_quality` schema only
- [ ] Repeating-group failures in UI (field id `test_results[n]`) — no dedicated panel copy yet

## Closure

**M3 backend + tests: done** (2026-05-19). **M3 product UI wireframe: partial** — track as M3.1 or UX milestone if needed.
