# Extraction Model — Discovery, Candidates, and Inconsistency

## Philosophy

Extraction is about **discovery**, not about validation. The extractor's job is to answer: "What is in this document?" — not "Is this document valid?"

This separation is fundamental. Extractors must not know about the schema. They produce a rich, exhaustive candidate pool. Downstream stages (mapping, resolution, validation) decide what to do with that pool.

---

## The Discovery Model

Extraction proceeds in two passes:

### Pass 1 — Discovery Pass

The discovery pass runs all extractors on all blocks. It is **schema-agnostic**: it does not know what fields the schema requires. It produces candidates for every recognizable entity in the document.

**Goal**: maximize recall. It is better to find too much than too little.

**What the discovery pass extracts**:
- Every key-value pair visible in the text (regex patterns)
- Every value that appears spatially related to a label (layout heuristics)
- All of the above scoped to their document section

**Section awareness**: The discovery pass operates within a section-aware context. Blocks are grouped by inferred section headings. This provides two benefits:
1. Ambiguity is contextualized: "temperature 18.5" in the "Fermentation" section and "temperature 22.0" in the "Bottling" section are both surfaced as candidates with different section labels — not silently merged.
2. Section context improves schema mapping: the schema can declare a `section_hint` for a field, guiding the mapping step.

### Pass 2 — Gap-Fill Pass

The gap-fill pass runs only for schema fields that were **not found** in the discovery pass. It is schema-aware: it knows exactly which fields are missing and uses targeted techniques to find them.

**Goal**: maximize schema coverage for missing fields without polluting the discovery results.

---

## Extraction Sources

Three extraction sources are defined in the system. They form a strict priority hierarchy:

| Source | Technique | Confidence Range | Priority |
|--------|-----------|-----------------|----------|
| `regex` | Anchored key-value patterns | 0.90–0.98 | Highest |
| `layout` | Spatial proximity heuristics | 0.50–0.75 | Middle |
| `llm` | LLM structured extraction | 0.35–0.45 | Lowest |

### Regex Extraction

Regex patterns are the most reliable source. They are anchored to specific label-value patterns in the text.

**Pattern types**:
- Label-colon: `Label: Value` → `(?i){label}\s*[:=]\s*({value_pattern})`
- Label with unit: `Label: Value unit` → `(?i){label}\s*[:=]\s*({value_pattern})\s*{unit}`
- Tabular: value appears on same line as label, separated by whitespace

**Schema-driven regex** (target architecture):
The schema declares regex patterns per field. The extractor uses them directly, rather than having hardcoded patterns in code. Example:

```json
{
  "fields": {
    "alcohol": {
      "type": "number",
      "aliases": ["Alcohol", "Alcohol %", "Alc.", "EtOH"],
      "regex_hint": "(?i)(alcohol|alc\\.)\\s*[:=]?\\s*([\\d.]+)\\s*%?"
    }
  }
}
```

This makes the extraction layer generic. No field names are hardcoded in extractor code.

### Layout Heuristics

Layout heuristics use the spatial relationship between blocks on the page. They are useful when labels and values are not on the same line or when formatting is irregular.

**Patterns**:
- **Same-line**: label keyword + number on the same line
- **Adjacent-line**: label on line N, value on line N+1 or N-1
- **Column-based**: label in left column (small x), value in right column (large x), same y-range

**Section-scoped**: layout heuristics consider section context. A value found in a different section than the expected one gets a lower confidence score.

### LLM Extraction

LLM extraction is a controlled fallback. It is used when regex and layout heuristics fail to find a value.

**Constraints** (non-negotiable):
- Temperature must be `0.0` — no randomness.
- Output must be structured JSON. No prose is accepted.
- The prompt must be fixed and versioned. Prompt changes are breaking changes.
- LLM results are labeled `source="llm"` with confidence ≤ 0.45 — always lower priority than regex/layout.
- LLM extraction is toggled by `settings.validation_llm_fallback_enabled`. Tests must disable it.

---

## ExtractionCandidate — Full Specification

```python
@dataclass(frozen=True)
class ExtractionCandidate:
    field: str                          # field name this candidate targets
    value: Any                          # typed extracted value
    source: str                         # "regex" | "layout" | "llm"
    confidence: float                   # 0.0 – 1.0
    block_id: str                       # source TextBlock.id
    page: int                           # source page (1-indexed)
    evidence_text: str                  # exact snippet that produced this value
    bbox: tuple[float,...] | None       # bounding box for visual highlight
    section_label: str | None           # inferred document section
```

**Immutability**: Candidates are frozen dataclasses. They are never modified after creation. If a downstream stage needs to adjust confidence (e.g. gap-fill assigns a penalty), it creates a new candidate.

---

## FieldCandidateMap — Full Specification

After schema mapping, candidates are grouped per schema field:

```python
@dataclass
class FieldEntry:
    status: Literal["found", "missing", "ambiguous"]
    candidates: list[ExtractionCandidate]

FieldCandidateMap = dict[str, FieldEntry]
```

**Status semantics**:

| Status | Meaning | Next step |
|--------|---------|-----------|
| `found` | Exactly 1 candidate (or 2+ with identical values) | Pass to resolution |
| `missing` | 0 candidates found | Trigger gap-fill |
| `ambiguous` | 2+ candidates with different values | Surface all; mark output AMBIGUOUS |

---

## Inconsistency Detection

### What counts as inconsistent?

Two candidates for the same field are **inconsistent** if their values differ beyond the type-appropriate epsilon:

| Type | Inconsistency threshold |
|------|------------------------|
| `number` | `abs(a - b) > 0.001` (configurable per field) |
| `string` | `normalize(a) != normalize(b)` (strip, lowercase) |
| `date` | `a != b` (exact match) |

Two candidates with the **same value** from different extractors or blocks are **not** inconsistent — they are duplicate evidence and are collapsed into a single `found` entry.

### Why AMBIGUOUS instead of picking the best?

The system could silently pick the highest-confidence candidate when multiple values are found. This is explicitly rejected for the following reason:

**Silent resolution of conflicting values is a compliance risk.** If a lab report mentions "temperature: 18°C" in one section and "temperature: 22°C" in another, the two values may refer to different measurements (fermentation temperature vs. storage temperature). Picking one silently hides this ambiguity from the validator. The correct behavior is to surface both, with context, and require human confirmation.

### How inconsistency is shown in the result

The `ValidationReport.ambiguous_fields` list contains every ambiguous field, with all candidates and their full evidence (text, block_id, page, bbox). The frontend renders these as an "inconsistency review" panel where the human can:
1. See each conflicting value highlighted in the PDF viewer.
2. Understand the section context for each candidate.
3. Accept one value manually (future: human-in-the-loop confirmation endpoint).

---

## Multi-Value Scenarios (Repeating Groups)

Some documents contain structured lists or tables where the same "field" appears dozens or hundreds of times — each representing a distinct test or measurement. For example:

```
Test Results:
  Parameter        | Value | Range
  ─────────────────────────────────
  pH               | 3.42  | 3.0–4.5
  Alcohol          | 11.2% | 8–15
  Residual Sugar   | 4.5   | 0–45
  ...
```

This is **not** an inconsistency — it is a **repeating group**. The schema declares a `group` field type to handle this case. The extractor recognizes the table structure and produces one candidate per row, tagged with a row index.

Repeating group handling is defined in `03_DOMAIN/RULE_ENGINE.md` and is scoped to Milestone 3.

---

## Extractor Extension Model (Target Architecture)

In the target architecture, extractors are **schema-driven plugins**, not hardcoded modules. This is the key refactor required after documentation.

**Current state** (Milestone 1): Extractors are hardcoded for the wine domain (`extractors_wine.py`). Field names, regex patterns, and layout heuristics are all specific to `ph`, `alcohol`, and `quality`.

**Target state** (post-M1 refactor): A generic `SchemaAwareExtractor` class reads field definitions from the schema body and generates extraction patterns at runtime:

```python
class SchemaAwareExtractor:
    def __init__(self, schema_body: dict):
        self.fields = schema_body["fields"]

    def extract(self, blocks: list[TextBlock]) -> list[ExtractionCandidate]:
        # For each field, try aliases + regex_hint + layout patterns
        ...
```

This means adding a new document type requires only a new schema — no new extractor code.

---

## Cross-References

| Topic | Document |
|-------|----------|
| Pipeline stage 2–4 algorithms | `01_ARCHITECTURE/PIPELINE_DESIGN.md` |
| Resolution from candidates | `03_DOMAIN/RESOLUTION_MODEL.md` |
| Schema field definition (aliases, regex_hint) | `03_DOMAIN/VALIDATION_SCHEMA.md` |
| Repeating group model | `03_DOMAIN/RULE_ENGINE.md` |
| Extractor code location | `05_IMPLEMENTATION/PIPELINE_IMPLEMENTATION.md` |
