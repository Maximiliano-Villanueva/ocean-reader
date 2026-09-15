# Validation test fixtures

## Wine corpus (M1–M3 regression)

| Path | Purpose |
|------|---------|
| `wine/corpus_index.json` | Manifest: expected PASS/FAIL/AMBIGUOUS per PDF |
| `wine/schema.json` | Default strict wine schema |
| `wine/clean/`, `wine/noisy/` | CSV-derived rows with rich multi-page PDFs |
| `wine/fail_schema/`, `wine/fail_missing/`, `wine/ambiguous/` | Synthetic edge cases |
| `wine/m3_cross_field/` | Cross-field rules corpus |
| `wine/schema_m3_wine_cross_field.json` | M3 schema |

Regenerate wine PDFs:

```bash
cd backend && uv run python tests/fixtures/wine/generate_fixtures.py
```

Requires `data/winequality-red.csv` at repo root for full corpus.

## Invoice corpus (DSL v3 + open-ended schema)

| Path | Purpose |
|------|---------|
| `invoice/corpus_index.json` | Invoice strict + cross-field expectations |
| `invoice/schema_invoice_v3.json` | Strict fields + `cross_field_rules` + `open_ended` |
| `invoice/inv_cursor_formatted.pdf` | **Showcase:** Factura header, sender/recipient columns, bordered table |
| `invoice/inv_clean_001.pdf` | PASS (same layout family) |
| `invoice/inv_fail_total.pdf` | FAIL cross-field total |

Regenerate:

```bash
cd backend && uv run python tests/fixtures/invoice/generate_invoice_fixtures.py
```

## Scanned / image PDFs (vision fallback)

When `VALIDATION_LLM_VISION_ENABLED=true`, the pipeline rasterizes pages and calls Ollama vision (`gemma4:e4b`) if layout text is sparse or required fields are missing. Snapshots record `extraction_meta.vision_fallback_used`.

## Pytest entry points

```bash
cd backend
uv run pytest tests/domain/validation/test_pipeline_wine_csv_fixtures.py -q
uv run pytest tests/domain/validation/test_invoice_corpus.py -q
uv run pytest tests/services/test_validation_pipeline_open_ended.py -q
uv run pytest tests/services/test_validation_pipeline_vision.py -q
```
