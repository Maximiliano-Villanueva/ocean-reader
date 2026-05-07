# Validation Schema — DSL Specification

## Purpose

The validation schema is the document that defines what a "valid" document looks like for a given project. It is the central artifact authored by users and consumed by the pipeline.

A schema has three concerns:
1. **Field declarations** — what fields to look for and their types
2. **Extraction hints** — how to find them (aliases, regex patterns, section context)
3. **Validation rules** — what constitutes a passing value

Schemas are versioned and managed by the Schema Management bounded context. See `03_DOMAIN/DOMAIN_MODEL.md` for lifecycle rules.

---

## Schema Body Structure (Full)

```json
{
  "version": "1",
  "fields": {
    "<field_name>": <FieldDefinition>
  },
  "rules": ["<rule_id>", ...],
  "cross_field_rules": [<CrossFieldRule>, ...],
  "groups": {
    "<group_name>": <GroupDefinition>
  }
}
```

| Key | Required | Description |
|-----|----------|-------------|
| `version` | no | DSL version for forward compatibility (default `"1"`) |
| `fields` | yes | Map of field name → field definition |
| `rules` | yes | List of rule IDs to apply globally (e.g. `"required"`, `"range_validation"`) |
| `cross_field_rules` | no | Rules involving multiple fields (Milestone 3) |
| `groups` | no | Repeating group definitions (Milestone 3) |

---

## FieldDefinition

```json
{
  "type": "number | string | date",
  "required": true | false,
  "min": <number>,
  "max": <number>,
  "aliases": ["<string>", ...],
  "regex_hint": "<regex>",
  "section_hint": "<section_name>",
  "tolerance": <number>
}
```

| Key | Required | Description |
|-----|----------|-------------|
| `type` | yes | Value type: `"number"`, `"string"`, `"date"` |
| `required` | no | If `true`, triggers `required` rule (default `false`) |
| `min` | no | Minimum value (number only); triggers `range_validation` if present |
| `max` | no | Maximum value (number only); triggers `range_validation` if present |
| `aliases` | no | Alternative labels for this field (e.g. `["Alc.", "Alcohol %", "EtOH"]`) |
| `regex_hint` | no | Custom regex pattern to extract this field's value. Group 1 (or last group) is the value. |
| `section_hint` | no | If set, extractor prioritizes candidates from the named document section |
| `tolerance` | no | For `range_validation`, the numeric epsilon for inconsistency detection (default `0.001`) |

**Example — full field definition**:
```json
{
  "alcohol": {
    "type": "number",
    "required": true,
    "min": 8.0,
    "max": 15.0,
    "aliases": ["Alcohol", "Alcohol %", "Alc.", "EtOH", "alcohol content"],
    "regex_hint": "(?i)(alcohol|alc\\.)\\s*[:=]?\\s*([\\d.]+)\\s*%?",
    "section_hint": "Chemical Analysis",
    "tolerance": 0.1
  }
}
```

---

## Minimal Milestone 1 Schema

This is the minimum viable schema format used in Milestone 1 (wine dataset):

```json
{
  "fields": {
    "ph": {
      "type": "number",
      "required": true
    },
    "alcohol": {
      "type": "number",
      "min": 8.0,
      "max": 15.0
    },
    "quality": {
      "type": "number",
      "min": 0,
      "max": 10
    }
  },
  "rules": ["required", "range_validation"]
}
```

---

## CrossFieldRule (Milestone 3)

```json
{
  "id": "<rule_id>",
  "expression": "<expression>",
  "error_message": "<message with {field} interpolation>",
  "fields": ["<field_a>", "<field_b>"]
}
```

| Key | Required | Description |
|-----|----------|-------------|
| `id` | yes | Unique rule identifier within the schema |
| `expression` | yes | Boolean expression using field names as variables |
| `error_message` | yes | Human-readable error message (supports `{field_name}` interpolation) |
| `fields` | no | Explicit list of fields involved (for evidence collection; inferred if absent) |

**Example**:
```json
{
  "id": "alcohol_quality_relationship",
  "expression": "quality >= 5 OR alcohol < 12",
  "error_message": "High-alcohol wine (≥12%) must have quality ≥ 5",
  "fields": ["alcohol", "quality"]
}
```

**Expression language** (safe subset):
- Field references: bare field names (`alcohol`, `quality`)
- Numeric literals: integers and floats
- Arithmetic: `+`, `-`, `*`, `/`
- Comparison: `>`, `>=`, `<`, `<=`, `==`, `!=`
- Boolean: `AND`, `OR`, `NOT` (case-insensitive)
- Parentheses for grouping

No function calls, no string operations, no external references. Expression is evaluated in a sandboxed interpreter.

---

## GroupDefinition (Milestone 3)

```json
{
  "section_hint": "<section_name>",
  "structure_hint": "table | list | sections",
  "row_fields": {
    "<field_name>": <FieldDefinition>
  },
  "row_rules": [<RowRule>]
}
```

| Key | Required | Description |
|-----|----------|-------------|
| `section_hint` | yes | The document section where the group is expected |
| `structure_hint` | no | Layout hint: `"table"` (columns), `"list"` (label: value per line), `"sections"` (mini-sections per item). Default: `"table"` |
| `row_fields` | yes | Field definitions for one row/item |
| `row_rules` | yes | Rules applied to each row independently |

**RowRule**:
```json
{
  "id": "<rule_id>",
  "expression": "<expression using row_fields>",
  "error_message": "<message>"
}
```

**Example — inspection test results group**:
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
          "id": "within_range",
          "expression": "lower_bound <= measured_value AND measured_value <= upper_bound",
          "error_message": "{parameter}: measured {measured_value} is outside [{lower_bound}, {upper_bound}]"
        }
      ]
    }
  }
}
```

---

## Schema Authoring Flow (LLM-Assisted)

The intended authoring workflow for non-technical users:

### Step 1 — Natural Language Input
The user describes what they want in plain language:
> "I need to validate wine lab reports. The report must have a pH between 3.0 and 4.5, alcohol content between 8% and 15%, and a quality score from 0 to 10. All three fields are required."

### Step 2 — LLM Translation
The system sends this description to the LLM with a structured prompt (temperature=0):

```
System: You are a schema generator. Convert the user's description into a JSON validation schema matching this DSL spec: [DSL_SPEC]. Output only valid JSON.

User: [user description]
```

LLM output:
```json
{
  "fields": {
    "ph": { "type": "number", "required": true, "min": 3.0, "max": 4.5 },
    "alcohol": { "type": "number", "required": true, "min": 8.0, "max": 15.0 },
    "quality": { "type": "number", "required": true, "min": 0, "max": 10 }
  },
  "rules": ["required", "range_validation"]
}
```

### Step 3 — UI Review
The user sees the generated schema in a structured form UI (not raw JSON). They can:
- Adjust any field's name, type, min, max, required flag
- Add aliases for better extraction
- Add or remove fields
- See a human-readable summary: "Field `alcohol` must be a number between 8 and 15"

### Step 4 — Save and Activate
On approval, the schema is saved as a new version. If a previous active version exists, it is archived automatically.

---

## Schema Validation Rules

Before saving, the schema body is validated:

- `fields` must be a non-empty object.
- Each field name must be a non-empty string with no spaces (underscore-separated).
- `type` must be one of `"number"`, `"string"`, `"date"`.
- `min` and `max` must be numbers when present; `min` must be ≤ `max`.
- `regex_hint` must be a valid Python regex pattern.
- `rules` must be a list of known rule IDs.
- `cross_field_rules[].expression` must parse in the safe expression evaluator.

Invalid schemas are rejected with a 422 error. The LLM-generated schema is always validated before saving.

---

## Versioning Semantics

| Change type | Action |
|-------------|--------|
| Adding a new field | New version (could turn previously-passing docs into FAIL) |
| Changing a range | New version |
| Fixing a typo in an alias | New version (affects extraction, could change results) |
| Adding an alias | New version |
| Changing error message text | New version (for auditability) |

There is no concept of a "patch" version that bypasses the version history. Every edit creates a new immutable version.

---

## Cross-References

| Topic | Document |
|-------|----------|
| Schema lifecycle | `03_DOMAIN/DOMAIN_MODEL.md` |
| Rule evaluation | `03_DOMAIN/RULE_ENGINE.md` |
| Extraction hints usage | `03_DOMAIN/EXTRACTION_MODEL.md` |
| API for schema management | `05_IMPLEMENTATION/API_SPEC.md` |
| Frontend schema editor | `05_IMPLEMENTATION/FRONTEND_SPEC.md` |
