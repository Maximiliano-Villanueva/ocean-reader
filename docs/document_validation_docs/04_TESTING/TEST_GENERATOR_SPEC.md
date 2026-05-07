# Test Generator Specification — Synthetic PDF Corpus Generation

## Purpose

The test generator converts wine dataset CSV rows into HTML documents and then into PDFs. It is run manually to populate the test fixture corpus. It must never be called automatically during test runs.

---

## Inputs

- `data/wine_quality.csv` — the source wine dataset
- `tests/fixtures/wine/schema.json` — the validation schema applied to all generated documents
- Row selection config (embedded in the script or passed as CLI args)

## Outputs

- `tests/fixtures/wine/clean/row_{N}_clean.html`
- `tests/fixtures/wine/clean/row_{N}_clean.pdf`
- `tests/fixtures/wine/clean/row_{N}_clean.json`
- `tests/fixtures/wine/noisy/row_{N}_noisy.html`
- `tests/fixtures/wine/noisy/row_{N}_noisy.pdf`
- `tests/fixtures/wine/noisy/row_{N}_noisy.json`
- `tests/fixtures/wine/corpus_index.json` — updated index

---

## Generation Pipeline

```
CSV row
   │
   ▼
[1] Extract wine fields (ph, alcohol, quality, + noise fields)
   │
   ▼
[2] Generate HTML — LLM prompt with temperature=0
   │        Two variants: clean + noisy
   ▼
[3] Convert HTML → PDF — Playwright headless browser
   │
   ▼
[4] Write ground truth JSON
   │
   ▼
[5] Update corpus_index.json
```

---

## Step 1 — Extract Fields

```python
def extract_row_data(row: dict) -> dict:
    return {
        "ph": float(row["pH"]),
        "alcohol": float(row["alcohol"]),
        "quality": int(row["quality"]),
        "noise": {
            "fixed_acidity": float(row["fixed acidity"]),
            "volatile_acidity": float(row["volatile acidity"]),
            "citric_acid": float(row["citric acid"]),
            "residual_sugar": float(row["residual sugar"]),
            "chlorides": float(row["chlorides"]),
            "free_sulfur_dioxide": float(row["free sulfur dioxide"]),
            "total_sulfur_dioxide": float(row["total sulfur dioxide"]),
            "density": float(row["density"]),
            "sulphates": float(row["sulphates"]),
        }
    }
```

---

## Step 2 — HTML Generation (LLM)

### Clean Document Prompt

```
System: You are a document generator. Generate a realistic HTML wine lab report.
        The document must contain exactly these values:
        - pH: {ph}
        - Alcohol: {alcohol}%
        - Quality: {quality}
        
        Requirements:
        - Simple layout, one section
        - Use a natural label for each field (e.g. "pH level:", "Alcohol content", "Quality score")
        - No other numeric values
        - Valid HTML, no external resources
        - No markdown fences, output raw HTML only

User: Generate the document.
```

### Noisy Document Prompt

```
System: You are a document generator. Generate a realistic HTML wine lab report.
        The document must contain exactly these values, somewhere in the text:
        - pH: {ph}
        - Alcohol: {alcohol}%
        - Quality: {quality}

        Additionally, include these as noise (in different sections, with different labels):
        {noise_fields}

        Requirements:
        - Multi-section layout (e.g. "Equipment Setup", "Chemical Analysis", "Sensory Panel")
        - Use varied labels: "Measured pH", "EtOH", "Alc.", "Quality score", "Panel rating", etc.
        - Mix table and paragraph formatting
        - Include at least 2 numeric values unrelated to the validation fields
        - Valid HTML, no external resources
        - No markdown fences, output raw HTML only

User: Generate the document.
```

### LLM Constraints

- **Temperature**: `0.0` — no randomness
- **Model**: the configured Ollama model (same as production fallback)
- **Max tokens**: 2048
- **Output**: raw HTML (no markdown fence). The script strips any accidental fences.

---

## Step 3 — HTML → PDF (Playwright)

```python
from playwright.async_api import async_playwright

async def html_to_pdf(html_content: str, output_path: str) -> None:
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.set_content(html_content)
        await page.pdf(
            path=output_path,
            format="A4",
            margin={"top": "20mm", "bottom": "20mm", "left": "20mm", "right": "20mm"},
            print_background=False,
        )
        await browser.close()
```

**Constraints**:
- Format: A4
- No external resources (fonts, images) — all must be inline or system fonts
- Consistent margins for predictable layout

---

## Step 4 — Ground Truth JSON

```python
def compute_expected_status(row_data: dict, schema: dict) -> tuple[str, list]:
    """Compute what the validation result should be for this row."""
    errors = []
    for field, spec in schema["fields"].items():
        value = row_data.get(field)
        if spec.get("required") and value is None:
            errors.append({"field": field, "rule": "required"})
        elif value is not None and "min" in spec and value < spec["min"]:
            errors.append({"field": field, "rule": "range_validation", "expected": [spec["min"], spec["max"]]})
        elif value is not None and "max" in spec and value > spec["max"]:
            errors.append({"field": field, "rule": "range_validation", "expected": [spec["min"], spec["max"]]})
    status = "FAIL" if errors else "PASS"
    return status, errors
```

---

## Step 5 — Corpus Index

`corpus_index.json` is a manifest of all generated fixtures:

```json
{
  "generated_at": "2026-05-01T10:00:00Z",
  "schema_version": "v1.0",
  "total": 100,
  "by_status": {
    "PASS": 72,
    "FAIL": 28
  },
  "entries": [
    {
      "csv_row": 42,
      "variant": "clean",
      "path": "clean/row_042_clean",
      "expected_status": "PASS"
    },
    {
      "csv_row": 42,
      "variant": "noisy",
      "path": "noisy/row_042_noisy",
      "expected_status": "PASS"
    }
  ]
}
```

---

## Running the Generator

```bash
cd backend

# Generate all fixtures (100 rows × 2 variants = 200 documents)
python tests/fixtures/wine/generate_fixtures.py

# Generate specific rows
python tests/fixtures/wine/generate_fixtures.py --rows 0,1,2,3,4

# Dry run (show prompts without generating)
python tests/fixtures/wine/generate_fixtures.py --dry-run

# Force regenerate (overwrite existing files)
python tests/fixtures/wine/generate_fixtures.py --force
```

---

## Idempotency

The generator is idempotent. Running it twice with the same CSV + same LLM model + temperature=0 produces identical output. This is guaranteed by:
- Deterministic LLM (temperature=0)
- Fixed prompts (versioned in the script)
- Fixed Playwright settings

---

## Cross-References

| Topic | Document |
|-------|----------|
| Dataset overview | `04_TESTING/DATASET_STRATEGY.md` |
| Wine pipeline end-to-end | `04_TESTING/WINE_DATASET_PIPELINE.md` |
| Test cases using generated fixtures | `04_TESTING/TEST_CASES.md` |
