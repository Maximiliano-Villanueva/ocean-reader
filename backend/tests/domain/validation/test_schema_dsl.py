"""M3 schema DSL validation (API rejects invalid ``cross_field_rules`` / ``groups``)."""

from __future__ import annotations

from ocean_read.domain.validation.schema_dsl import collect_schema_dsl_errors


def test_schema_dsl_empty_ok() -> None:
    assert collect_schema_dsl_errors({"fields": {}, "rules": []}) == []


def test_schema_dsl_m3_requires_version_2_when_cross_field_present() -> None:
    body = {
        "fields": {"a": {"type": "number"}},
        "rules": [],
        "cross_field_rules": [{"id": "x", "expression": "a > 0", "error_message": "m", "fields": ["a"]}],
    }
    errs = collect_schema_dsl_errors(body)
    assert any("version" in e.lower() and "2" in e for e in errs)


def test_schema_dsl_cross_field_bad_expression() -> None:
    body = {
        "version": "2",
        "fields": {"a": {"type": "number"}},
        "rules": [],
        "cross_field_rules": [{"id": "x", "expression": "(", "error_message": "m", "fields": ["a"]}],
    }
    errs = collect_schema_dsl_errors(body)
    assert any("invalid expression" in e for e in errs)


def test_schema_dsl_cross_field_unknown_field_in_expr() -> None:
    body = {
        "version": "2",
        "fields": {"a": {"type": "number"}},
        "rules": [],
        "cross_field_rules": [
            {"id": "x", "expression": "a > 0 AND b > 0", "error_message": "m", "fields": ["a"]}
        ],
    }
    errs = collect_schema_dsl_errors(body)
    assert any("b" in e and "unknown" in e for e in errs)


def test_schema_dsl_group_row_rule_unknown_row_field() -> None:
    body = {
        "version": "2",
        "fields": {},
        "rules": [],
        "groups": {
            "g1": {
                "section_hint": "Sec",
                "row_fields": {"x": {"type": "number"}},
                "row_rules": [{"id": "r1", "expression": "y > 0", "error_message": "bad"}],
            }
        },
    }
    errs = collect_schema_dsl_errors(body)
    assert any("unknown row field 'y'" in e for e in errs)


def test_schema_dsl_group_invalid_structure_hint() -> None:
    body = {
        "version": "2",
        "fields": {},
        "rules": [],
        "groups": {
            "g1": {
                "section_hint": "Sec",
                "structure_hint": "grid",
                "row_fields": {"x": {"type": "number"}},
                "row_rules": [],
            }
        },
    }
    errs = collect_schema_dsl_errors(body)
    assert any("structure_hint" in e and "grid" in e for e in errs)
