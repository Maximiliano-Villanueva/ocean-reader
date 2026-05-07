# Rule Engine — Validation Rules, DSL, and Extensibility

## Purpose

The rule engine applies schema-declared rules to the `ResolvedDocument` and produces a list of `ValidationError`s. It is a pure function with no I/O.

A rule is a predicate: given a field's resolved value and the rule's parameters, it returns `pass` or `fail`. The engine iterates all rules declared in the schema, evaluates each, and collects failures.

---

## Rule Execution Model

```
for each rule_id in schema.rules:
    for each field in schema.fields:
        if rule_id applies to this field:
            result = evaluate(rule_id, field, resolved_value, rule_params)
            if result == FAIL:
                emit ValidationError
```

Rules are evaluated independently. The engine does not short-circuit on the first failure. All failures are collected and returned. This ensures a complete picture of what's wrong with a document.

---

## Milestone 1 Rules

### Rule: `required`

**Description**: The field must be present in the `ResolvedDocument`. A field is "present" if it was extracted and resolved to a non-null value.

**Schema declaration**: triggered by `"required": true` on a field definition.

**Evaluation**:
```
if field_name not in resolved_document:
    FAIL: expected = "present", value = None
```

**Evidence**: None — a missing field has no location in the document.

**Example schema**:
```json
{
  "fields": {
    "ph": { "type": "number", "required": true }
  }
}
```

---

### Rule: `range_validation`

**Description**: A numeric field's value must satisfy `min ≤ value ≤ max`.

**Schema declaration**: `"min"` and/or `"max"` on a field of `"type": "number"`.

**Evaluation**:
```
if value < min OR value > max:
    FAIL: expected = [min, max], value = actual_value
```

**Type coercion**: If the resolved value is not numeric, the rule fails with `expected = [min, max], value = raw_value`.

**One-sided ranges**: Both `min` and `max` are optional. If only `min` is declared, only the lower bound is enforced. Same for `max`.

**Evidence**: The evidence from the resolved field (the block where the value was found).

**Example schema**:
```json
{
  "fields": {
    "alcohol": { "type": "number", "min": 8.0, "max": 15.0 }
  },
  "rules": ["range_validation"]
}
```

---

### Rule: `type_check`

**Description**: The resolved value must be coercible to the declared type.

**Supported types**:
| Type | Valid if |
|------|---------|
| `number` | Value is int or float, or a string parseable as float |
| `string` | Value is any non-null string |
| `date` | Value is parseable as ISO 8601 date |

**Evidence**: The block where the value was found.

---

## Milestone 3 Rules

### Rule: `cross_field`

**Description**: An expression involving two or more fields must evaluate to true.

**Schema declaration**:
```json
{
  "cross_field_rules": [
    {
      "id": "alcohol_sugar_ratio",
      "expression": "alcohol / residual_sugar > 2.0",
      "error_message": "Alcohol-to-sugar ratio must exceed 2.0"
    }
  ]
}
```

**Expression language**: A restricted DSL supporting:
- Arithmetic: `+`, `-`, `*`, `/`
- Comparison: `>`, `>=`, `<`, `<=`, `==`, `!=`
- Field references: bare field names (e.g. `alcohol`)
- Literals: numeric and string

**Safety**: Expressions are evaluated in a sandboxed interpreter (no `eval`). Only declared field names and numeric operations are permitted.

**Evidence**: The evidence refs of all fields involved in the expression are included in the error.

---

### Rule: `repeating_group`

**Description**: A template rule applied to every row of a detected table or list section in the document.

**Use case**: An inspection report has 200 test items. Each item has a `parameter_name`, `measured_value`, and `acceptable_range`. The schema declares one rule template that applies to every row.

**Schema declaration**:
```json
{
  "groups": {
    "test_results": {
      "section_hint": "Test Results",
      "row_fields": {
        "parameter": { "type": "string" },
        "value": { "type": "number" },
        "lower_bound": { "type": "number" },
        "upper_bound": { "type": "number" }
      },
      "row_rules": [
        {
          "id": "row_range",
          "expression": "lower_bound <= value <= upper_bound",
          "error_message": "{parameter} value {value} is outside range [{lower_bound}, {upper_bound}]"
        }
      ]
    }
  }
}
```

**Extraction**: The extractor recognizes the table structure in `section_hint` and produces one candidate set per row. Each row is independently resolved and validated.

**Result**: One `ValidationError` per row that fails, with the row's evidence.

**Schema flexibility note**: The repeating group schema supports several structural patterns:
- **Explicit table** (labeled columns with header row)
- **Label-value list** (each item is `Label: Value` on its own line)
- **Section-per-item** (each item is a mini-section with sub-fields)

The `structure_hint` field on the group declaration guides the extractor on which pattern to use.

---

### Rule: `reference_lookup` (Future)

**Description**: A field's value must appear in a declared reference dataset (e.g. approved supplier codes, valid product categories).

**Schema declaration**:
```json
{
  "fields": {
    "supplier_code": {
      "type": "string",
      "reference": {
        "dataset": "approved_suppliers",
        "column": "code"
      }
    }
  }
}
```

Reference datasets are project-scoped and managed separately. This feature is not in the current milestones but the schema DSL is designed to accommodate it.

---

## Rule Registry Pattern

Rules are registered by ID. Adding a new rule means:
1. Implementing a `RuleEvaluator` class with an `evaluate(field, value, params, evidence) → ValidationError | None` method.
2. Registering it in the `RuleRegistry` under its ID.
3. Declaring it in a schema's `rules` array.

No changes to the pipeline or engine are required.

```python
class RuleRegistry:
    _rules: dict[str, RuleEvaluator] = {}

    @classmethod
    def register(cls, rule_id: str, evaluator: RuleEvaluator):
        cls._rules[rule_id] = evaluator

    @classmethod
    def get(cls, rule_id: str) -> RuleEvaluator:
        if rule_id not in cls._rules:
            raise UnknownRuleError(f"Rule {rule_id!r} is not registered")
        return cls._rules[rule_id]
```

Built-in rules (`required`, `range_validation`, `type_check`, `cross_field`, `repeating_group`) are registered at module load time.

---

## Engine Contract (Non-Negotiable)

- **Pure function**: `validate(resolved_document, schema_body) → list[ValidationError]`
- **No I/O**: no database, no LLM, no file reads inside the engine.
- **All failures returned**: never short-circuit.
- **Evidence must come from ResolvedDocument**: the engine does not re-read the PDF.
- **Same inputs → same outputs**: engine is fully deterministic.

---

## Cross-References

| Topic | Document |
|-------|----------|
| Schema DSL for rule declaration | `03_DOMAIN/VALIDATION_SCHEMA.md` |
| Pipeline stage 7 | `01_ARCHITECTURE/PIPELINE_DESIGN.md` |
| ValidationError definition | `03_DOMAIN/DOMAIN_MODEL.md` |
| Engine code location | `05_IMPLEMENTATION/PIPELINE_IMPLEMENTATION.md` |
| Cross-field and repeating group milestone | `02_MILESTONES/MILESTONE_3_ADVANCED_RULES.md` |
