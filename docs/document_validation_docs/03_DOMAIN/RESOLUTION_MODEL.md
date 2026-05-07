# Resolution Model — Deterministic Candidate Selection

## Purpose

Resolution takes the `FieldCandidateMap` (from schema mapping) and produces a `ResolvedDocument` — a flat map with exactly one value per field.

Resolution only operates on fields with `status = "found"`. Fields with `status = "missing"` or `status = "ambiguous"` bypass resolution:
- `missing` → no value in `ResolvedDocument`; validation will raise a `required` error.
- `ambiguous` → entire document receives `AMBIGUOUS` status; validation is not attempted.

---

## Priority Hierarchy

Resolution is priority-based. Source priority is fixed and non-configurable:

| Rank | Source | Rationale |
|------|--------|-----------|
| 1 (highest) | `regex` | Anchored label-value patterns; least likely to be wrong |
| 2 | `layout` | Spatial heuristics; reliable in semi-structured docs |
| 3 (lowest) | `llm` | LLM output; valuable fallback but lowest certainty |

**Within the same source** (tie-breaking, in order):

1. **Highest confidence** — the confidence score assigned by the extractor (float 0.0–1.0)
2. **First in document order** — lowest `block_id` index (i.e. `b3` wins over `b12`)

This ensures the resolution is fully deterministic: identical inputs → identical winner, every time.

---

## Resolution Algorithm

```python
def resolve_field_candidate(field: str, candidates: list[ExtractionCandidate]) -> ExtractionCandidate:
    same_field = [c for c in candidates if c.field == field]

    if not same_field:
        raise ValueError(f"No candidates for field {field!r}")

    def sort_key(c: ExtractionCandidate) -> tuple[int, float, str]:
        priority = SOURCE_PRIORITY.get(c.source.lower(), 0)
        # Negate: higher priority/confidence sorts first
        return (-priority, -c.confidence, c.block_id)

    ordered = sorted(same_field, key=sort_key)
    return ordered[0]
```

**Sort key breakdown**:
- `-priority`: regex (3) > layout (2) > llm (1) → negated so highest sorts first
- `-confidence`: 0.95 > 0.55 → negated so highest sorts first
- `block_id`: lexicographic ascending — `"b3"` < `"b12"` (note: block IDs are `b{int}`, compare numerically)

**Block ID tie-breaking**: Since block IDs are `b0`, `b1`, ..., `b99`, `b100`, simple string comparison would be incorrect (`"b9" > "b10"` lexicographically). The sort must compare the integer suffix.

---

## Resolution Output

```python
@dataclass(frozen=True)
class ResolvedField:
    value: Any
    evidence: EvidenceRef

ResolvedDocument = dict[str, ResolvedField]
```

The evidence attached to the winning candidate becomes the `EvidenceRef` for that field. This evidence propagates into `ValidationError` if the field fails validation.

---

## Evidence Propagation

The winner candidate's evidence fields are passed forward:

| Candidate field | → | EvidenceRef field |
|-----------------|---|------------------|
| `evidence_text` | → | `text` |
| `block_id` | → | `block_id` |
| `page` | → | `page` |
| `bbox` | → | `bbox` |

This is the chain of custody from PDF → extracted text → resolved value → validation error → API response. Every step is traceable.

---

## What Resolution Does NOT Do

Resolution must not:

- **Merge or average values** — if there are two `"found"` candidates with different values, resolution should not run (that's an inconsistency, handled by Stage 5).
- **Make probabilistic choices** — no sampling, no randomness.
- **Call I/O** — no database reads, no LLM calls. It is a pure sorting function.
- **Know about schema rules** — resolution is value-selection only. Whether the selected value passes a range rule is the validation engine's concern.

---

## Example Trace

**Input candidates for field `"alcohol"`**:

```
candidates = [
  ExtractionCandidate(field="alcohol", value=11.2, source="regex",  confidence=0.95, block_id="b3", ...),
  ExtractionCandidate(field="alcohol", value=11.2, source="layout", confidence=0.55, block_id="b3", ...),
  ExtractionCandidate(field="alcohol", value=11.2, source="llm",    confidence=0.40, block_id="b0", ...),
]
```

**Sort keys**:
```
regex  candidate: (-3, -0.95, "b3")  ← wins (lowest tuple)
layout candidate: (-2, -0.55, "b3")
llm    candidate: (-1, -0.40, "b0")
```

**Winner**: `regex` candidate. Value = `11.2`. Evidence = block `b3`.

---

## Reproducibility Guarantee

Given a fixed PDF and a fixed schema, the resolution output is deterministic:

1. PDF → same TextBlocks (PyMuPDF is deterministic given same input)
2. TextBlocks → same candidates (regex and layout are deterministic; LLM uses temperature=0)
3. Candidates → same winner (sort key is fully deterministic)

This means: the same document submitted twice always produces the same `ResolvedDocument`, and therefore the same `ValidationReport`.

---

## Cross-References

| Topic | Document |
|-------|----------|
| Stage 6 in pipeline | `01_ARCHITECTURE/PIPELINE_DESIGN.md` |
| ExtractionCandidate definition | `03_DOMAIN/EXTRACTION_MODEL.md` |
| EvidenceRef definition | `03_DOMAIN/DOMAIN_MODEL.md` |
| Resolution code location | `05_IMPLEMENTATION/PIPELINE_IMPLEMENTATION.md` |
