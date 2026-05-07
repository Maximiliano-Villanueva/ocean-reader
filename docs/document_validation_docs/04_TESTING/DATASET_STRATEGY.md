# Dataset Strategy — Synthetic Document Corpus

## Philosophy

Validation of this system cannot rely on manual inspection or real-world PDFs. The testing strategy requires:

- **Known ground truth**: we must know the correct answer before running the test
- **Deterministic generation**: the same input always produces the same PDF
- **Variety**: layouts, wording, noise, and edge cases must be covered
- **Reusability**: PDFs are generated once and stored; they are never regenerated in tests

The wine dataset is the primary corpus for Milestone 1. It is a proxy for real-world lab reports — small, well-understood, and with clear numeric fields.

---

## Primary Dataset: Wine Quality (Milestone 1)

**Source**: UCI Machine Learning Repository — Wine Quality Dataset (CSV)

**Fields used**:

| CSV column | Schema field | Type | Range used in schema |
|-----------|--------------|------|---------------------|
| `pH` | `ph` | number | 2.5 – 4.5 |
| `alcohol` | `alcohol` | number | 8.0 – 15.0 |
| `quality` | `quality` | number | 0 – 10 |

Additional columns exist in the CSV but are not validated in Milestone 1. They are used as noise content in noisy documents.

**Dataset size**: ~1,600 rows (red wine). We use a deterministic 50-row sample for the test corpus.

**Row selection**: Rows are selected to cover all test case categories:
- Rows where all 3 fields are within schema ranges → PASS documents
- Rows where `alcohol > 15` → FAIL on `range_validation`
- Rows where `quality` is missing from the generated document → FAIL on `required`
- Rows with noise that includes extra numbers → tests noise robustness

---

## Document Types Per Row

Each CSV row generates **two document variants**:

### 1. Clean Document

Contains only the relevant data in a simple, unambiguous layout:

```html
<div>
  <h1>Wine Quality Analysis</h1>
  <p>pH: 3.42</p>
  <p>Alcohol: 11.2%</p>
  <p>Quality score: 6</p>
</div>
```

**Purpose**: Tests basic extraction accuracy.

### 2. Noisy Document

Contains the same relevant data plus:
- Irrelevant numbers (temperatures, dates, equipment codes)
- Alternative field labels ("Alc.", "EtOH", "measured pH")
- Mixed formatting (tables, paragraphs, lists)
- Multiple sections with different content

```html
<div>
  <h1>Wine Lab Report #2041</h1>
  <p>Equipment calibrated at: 22.5°C on 2026-01-15</p>
  <h2>Chemical Analysis</h2>
  <table>
    <tr><td>Measured pH</td><td>3.42</td></tr>
    <tr><td>EtOH content</td><td>11.2%</td></tr>
  </table>
  <h2>Sensory Panel</h2>
  <p>Panel size: 8 tasters. Average quality score: 6</p>
  <p>Sample temperature: 18°C. Room humidity: 65%</p>
</div>
```

**Purpose**: Tests extraction robustness and noise resistance.

---

## Ground Truth Format

For each document, a ground truth JSON is stored alongside the PDF:

```json
{
  "csv_row": 42,
  "variant": "noisy",
  "expected": {
    "ph": 3.42,
    "alcohol": 11.2,
    "quality": 6.0
  },
  "expected_status": "PASS",
  "expected_errors": []
}
```

For a FAIL case:
```json
{
  "csv_row": 17,
  "variant": "clean",
  "expected": {
    "ph": 3.1,
    "alcohol": 18.4,
    "quality": 5.0
  },
  "expected_status": "FAIL",
  "expected_errors": [
    {
      "field": "alcohol",
      "rule": "range_validation",
      "expected": [8.0, 15.0]
    }
  ]
}
```

---

## Corpus Structure on Disk

```
backend/tests/fixtures/wine/
├── corpus_index.json          — index of all fixtures (row, variant, expected status)
├── schema.json                — the wine validation schema used for this corpus
├── clean/
│   ├── row_042_clean.html     — generated HTML (stored, not regenerated)
│   ├── row_042_clean.pdf      — generated PDF (stored, not regenerated)
│   ├── row_042_clean.json     — ground truth
│   ├── ...
└── noisy/
    ├── row_042_noisy.html
    ├── row_042_noisy.pdf
    ├── row_042_noisy.json
    ├── ...
```

---

## Fixture Generation Rules

1. **Generate once**: Run `python tests/fixtures/wine/generate_fixtures.py` to create all HTMLs + PDFs. This script must be run manually when the corpus needs to change.
2. **Deterministic**: The LLM is called with `temperature=0`. Same CSV row always produces the same HTML.
3. **HTML is the source of truth**: PDFs are derived from HTML via Playwright. If the HTML is regenerated, the PDF must be regenerated too.
4. **Never regenerate in tests**: Tests load pre-generated PDFs from disk. The generation script is never called during test execution.
5. **Version the corpus**: The corpus is committed to the repository. If fixtures are updated, the commit must include both the new HTML/PDF files and updated ground truth JSONs.

---

## Future Dataset Expansion (Milestone 3+)

- Real-world PDFs (anonymized) from partner labs
- COA documents with repeating group tables
- Inspection checklists
- Multi-page documents
- Documents with mixed text and image content

---

## Cross-References

| Topic | Document |
|-------|----------|
| Test generator spec | `04_TESTING/TEST_GENERATOR_SPEC.md` |
| Wine dataset pipeline | `04_TESTING/WINE_DATASET_PIPELINE.md` |
| Test cases | `04_TESTING/TEST_CASES.md` |
| Test strategy | `04_TESTING/TEST_STRATEGY.md` |
