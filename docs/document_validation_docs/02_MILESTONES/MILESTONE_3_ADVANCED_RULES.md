# MILESTONE 3 — ADVANCED VALIDATION RULES

## Objective

Extend the validation engine to support rules that operate beyond single-field checks. Specifically:

1. **Cross-field rules**: conditions involving two or more fields
2. **Repeating group validation**: template rules applied to every row of a table or list section
3. **Schema DSL extensions**: UI support for authoring these new rule types

---

## Scope

### Included

- Cross-field rule evaluation engine
- Safe expression evaluator (no `eval`)
- Repeating group extraction and validation
- Schema DSL extensions for both rule types
- Schema editor UI updates (form-based authoring for new rule types)
- Test dataset expansion (wine + cross-field cases)

### Excluded

- Reference data lookups (future milestone)
- Statistical rules (e.g. mean across multiple rows)
- Machine learning-based rule generation

---

## Part 1: Cross-Field Rules

### Motivation

Many compliance checks involve relationships between fields, not just individual field values. Examples:

- Wine: if alcohol ≥ 12%, then quality must be ≥ 5
- Lab report: total sulphur dioxide must be ≥ free sulphur dioxide
- Inspection: if defect count > 0, then defect description must be present

These cannot be expressed as single-field range or required rules. They need a cross-field evaluation model.

---

### Schema Declaration

```json
{
  "fields": {
    "alcohol": { "type": "number", "min": 8.0, "max": 15.0 },
    "quality": { "type": "number", "min": 0, "max": 10 },
    "free_sulfur_dioxide": { "type": "number" },
    "total_sulfur_dioxide": { "type": "number" }
  },
  "rules": ["range_validation"],
  "cross_field_rules": [
    {
      "id": "high_alcohol_quality",
      "expression": "quality >= 5 OR alcohol < 12",
      "error_message": "Wine with alcohol ≥ 12% must have quality ≥ 5",
      "fields": ["alcohol", "quality"]
    },
    {
      "id": "sulfur_dioxide_order",
      "expression": "total_sulfur_dioxide >= free_sulfur_dioxide",
      "error_message": "Total sulphur dioxide ({total_sulfur_dioxide}) must be ≥ free ({free_sulfur_dioxide})",
      "fields": ["free_sulfur_dioxide", "total_sulfur_dioxide"]
    }
  ]
}
```

---

### Expression Language

The expression language is a safe, restricted DSL. It is evaluated by a custom interpreter — no Python `eval`, no `exec`.

**Supported operators**:
- Arithmetic: `+`, `-`, `*`, `/`
- Comparison: `>`, `>=`, `<`, `<=`, `==`, `!=`
- Boolean: `AND`, `OR`, `NOT` (case-insensitive)
- Parentheses for grouping
- Field references: bare field names from `fields`
- Numeric literals: integers and floats

**Not supported** (by design):
- String operations
- Function calls
- External variable references
- Python expressions of any kind

**Evaluation**:
1. Parse expression to AST using a custom parser.
2. Substitute field values from `ResolvedDocument`.
3. Evaluate AST — returns boolean.
4. If `False` → emit `ValidationError` with the rule's `error_message`.

**Missing fields in cross-field rules**: If any field referenced in a cross-field rule is missing from `ResolvedDocument`, the rule is skipped (the `required` rule for that field will already produce an error). This avoids double-counting failures.

**Error message interpolation**: `{field_name}` in `error_message` is replaced with the resolved value:
- Input: `"Total sulphur dioxide ({total_sulfur_dioxide}) must be ≥ free ({free_sulfur_dioxide})"`
- Output: `"Total sulphur dioxide (155) must be ≥ free (46)"`

**Evidence**: Cross-field errors include the evidence refs of all involved fields.

---

### Implementation

**New file**: `ocean_read/domain/validation/expression_evaluator.py`

```python
class ExpressionEvaluator:
    """Safe, sandboxed evaluator for cross-field rule expressions."""

    def evaluate(
        self,
        expression: str,
        bindings: dict[str, float | str],
    ) -> bool:
        """
        Evaluate expression with field values substituted.
        Returns True (passes) or False (fails).
        Raises ExpressionEvaluationError on syntax/type errors.
        """
        ast = self._parse(expression)
        return self._eval(ast, bindings)
```

**Registration**: `CrossFieldRule` evaluator is registered in `RuleRegistry`.

---

## Part 2: Repeating Group Validation

### Motivation

Many document types contain structured lists or tables where the same validation rule must apply to every row. Examples:

- An inspection report with 200 test items, each with a measured value and an acceptable range
- A COA with a table of 50 physical/chemical parameters
- A QA checklist with 30 line items, each pass/fail

The schema declares the structure of one "row" and the rules that apply. The engine extracts all rows and validates each one independently.

---

### Schema Declaration

```json
{
  "groups": {
    "test_results": {
      "section_hint": "Test Results",
      "structure_hint": "table",
      "row_fields": {
        "parameter": { "type": "string" },
        "measured_value": { "type": "number" },
        "lower_bound": { "type": "number" },
        "upper_bound": { "type": "number" }
      },
      "row_rules": [
        {
          "id": "within_spec",
          "expression": "lower_bound <= measured_value AND measured_value <= upper_bound",
          "error_message": "{parameter}: measured {measured_value} is outside spec [{lower_bound}, {upper_bound}]"
        }
      ]
    }
  }
}
```

---

### Structure Hints

| `structure_hint` | Expected layout | Extraction strategy |
|-----------------|----------------|---------------------|
| `"table"` | Header row + data rows with column alignment | Column-based extraction using bbox x-coordinates |
| `"list"` | Each row is `Label: Value` on its own line | Per-line label-value extraction |
| `"sections"` | Each item is a mini-section with sub-fields | Section-scoped extraction per item |

The `section_hint` tells the extractor which document section to scan for the group. Only blocks within that section are considered.

---

### Extraction Model for Repeating Groups

Repeating group extraction extends `SchemaAwareExtractor`:

```python
def extract_group(
    self,
    blocks: list[TextBlock],
    group_name: str,
    group_spec: dict,
) -> list[dict[str, ExtractionCandidate]]:
    """
    Extract all rows of a repeating group.
    Returns a list of dicts, one per row, mapping row_field_name → candidate.
    """
    section_blocks = self._filter_by_section(blocks, group_spec["section_hint"])
    structure = group_spec.get("structure_hint", "table")

    if structure == "table":
        return self._extract_table_rows(section_blocks, group_spec["row_fields"])
    elif structure == "list":
        return self._extract_list_rows(section_blocks, group_spec["row_fields"])
    elif structure == "sections":
        return self._extract_section_rows(section_blocks, group_spec["row_fields"])
```

---

### Validation Model for Repeating Groups

Each row is independently resolved and validated:

```python
def validate_group(
    self,
    rows: list[dict[str, ExtractionCandidate]],
    group_spec: dict,
) -> list[ValidationError]:
    errors = []
    for row_idx, row_candidates in enumerate(rows):
        resolved_row = resolve_row(row_candidates)
        for rule in group_spec["row_rules"]:
            result = self._eval_expression(rule["expression"], resolved_row)
            if not result:
                errors.append(ValidationError(
                    field=f"{group_name}[{row_idx}]",
                    value=resolved_row,
                    expected=rule["expression"],
                    rule=rule["id"],
                    evidence=collect_row_evidence(row_candidates),
                ))
    return errors
```

**Error field naming**: Errors for repeating group rows use `"{group_name}[{row_index}]"` as the field identifier (e.g. `"test_results[14]"`). This makes it clear which row failed.

---

## Part 3: Schema DSL Extensions

### DSL Version

`"version": "2"` activates Milestone 3 features. Version `"1"` schemas remain valid and are processed with M1 rules only.

### Schema Validation

The schema body validator (`SchemaBodyValidator`) gains new checks:

- `cross_field_rules[].expression` must parse successfully in the `ExpressionEvaluator`.
- All field references in expressions must exist in `fields`.
- `groups[].section_hint` must be a non-empty string.
- `groups[].row_fields` must be valid field definitions.
- `groups[].row_rules[].expression` must parse successfully.

---

## Part 4: UI for Advanced Rules

### Cross-Field Rules in Schema Editor

The schema editor's "Review" step gains a new section below the field list:

```
┌─ Cross-field rules ──────────────────────────────────────────────────┐
│                                                                      │
│  ┌── high_alcohol_quality ──────────────────────────────────────────┐│
│  │ When: alcohol >= 12                                              ││
│  │ Then: quality >= 5                                               ││
│  │ Error: "Wine with alcohol ≥ 12% must have quality ≥ 5"          ││
│  │ [Edit] [Delete]                                                  ││
│  └──────────────────────────────────────────────────────────────────┘│
│                                                                      │
│  [+ Add cross-field rule]                                            │
└──────────────────────────────────────────────────────────────────────┘
```

The "Add cross-field rule" flow allows the user to:
1. Enter a natural language description ("If alcohol is ≥ 12%, quality must be at least 5")
2. LLM generates the expression
3. User reviews and approves

### Repeating Groups in Schema Editor

A "Groups" section in the schema editor allows declaring table/list validation:

```
┌─ Repeating Groups ───────────────────────────────────────────────────┐
│                                                                      │
│  ┌── test_results ─────────────────────────────────────────────────┐│
│  │ Section: "Test Results"    Structure: Table                     ││
│  │ Row fields: parameter (string), measured_value, lower, upper    ││
│  │ Rules: within_spec (lower <= measured_value <= upper)           ││
│  │ [Edit] [Delete]                                                  ││
│  └──────────────────────────────────────────────────────────────────┘│
│                                                                      │
│  [+ Add group]                                                       │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Test Cases for Milestone 3

### Cross-Field Rule Tests

| Test | Input | Expected |
|------|-------|---------|
| Both fields pass independently, cross-rule satisfied | `alcohol=11, quality=6` | PASS |
| Both fields pass individually, cross-rule fails | `alcohol=13, quality=4` | FAIL (high_alcohol_quality) |
| Referenced field missing (skip cross-rule) | `alcohol=13, quality=null` | FAIL (required on quality) |
| Cross-rule with arithmetic passes | `total_so2=155, free_so2=46` | PASS |
| Cross-rule with arithmetic fails | `total_so2=30, free_so2=46` | FAIL (sulfur_dioxide_order) |

### Repeating Group Tests

| Test | Input | Expected |
|------|-------|---------|
| All rows within spec | 10 rows, all `lower <= measured <= upper` | PASS |
| 1 row out of spec | Row 7: `measured=105, upper=100` | FAIL (test_results[6]) |
| Multiple rows out of spec | Rows 3, 7, 12 fail | FAIL with 3 errors |
| Empty group (no rows found) | No table in section | FAIL (group "test_results" not found) |

---

## Definition of Done

Milestone 3 is complete when:

- Cross-field rules evaluate correctly for all test cases.
- Repeating group extraction and validation work for **table**, **list**, and **sections** structures.
- Schema editor supports authoring both rule types (**forms** + optional **LLM assist** for cross-field expressions when enabled).
- All new rule types have unit tests.
- Wine dataset includes a bundled M3 schema fixture exercised by the validation pipeline tests.
- Expression evaluator has no `eval` — fully sandboxed.

---

## Implementation status (engineering)

| Area | Status | Notes |
|------|--------|--------|
| Cross-field expressions | **Done** | `expression_evaluator.py` — recursive-descent AST, no `eval` / `exec`. |
| Cross-field in rule engine | **Done** | `engine.validate_schema` when `"version": "2"`. |
| Repeating groups | **Done** | `repeating_groups.py`: **table**, **list**, **sections**; section body after header line for layout PDFs. |
| Schema DSL validation | **Done** | `schema_dsl.collect_schema_dsl_errors`; API **400** on publish if errors. |
| Schema editor UI | **Partial** | `ProjectSchemasPage`: JSON + append forms + LLM suggest — not full Part 4 card wireframe. |
| Wine + cross-field fixtures | **Done** | `schema_m3_wine_cross_field.json`, `m3_corpus_index.json`, `m3_cross_field/*.pdf`; `generate_fixtures.py --m3-only`. |
| Pipeline E2E | **Done** | `test_validation_pipeline_m3.py` (cross-field + list group on PDF); `test_pipeline_m3_corpus.py`. |
| LLM expression assist | **Done** (opt-in) | `VALIDATION_SCHEMA_LLM_ASSIST_ENABLED` + Ollama. |
| Tests | **Done** | See [`M3_CHECKLIST.md`](../../project_management/M3_CHECKLIST.md). |

**Tracker:** [`docs/project_management/M3_CHECKLIST.md`](../../project_management/M3_CHECKLIST.md).

---

## Cross-References

| Topic | Document |
|-------|----------|
| Rule engine base | `03_DOMAIN/RULE_ENGINE.md` |
| Schema DSL | `03_DOMAIN/VALIDATION_SCHEMA.md` |
| Extraction model (groups) | `03_DOMAIN/EXTRACTION_MODEL.md` |
| Frontend schema editor | `05_IMPLEMENTATION/FRONTEND_SPEC.md` |
