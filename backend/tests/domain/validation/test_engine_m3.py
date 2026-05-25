"""M3 cross-field rules integrated in ``validate_schema``."""

from __future__ import annotations

from ocean_read.domain.validation.engine import validate_schema
from ocean_read.domain.validation.pdf_blocks import TextBlock


def _wine_like_fields() -> dict:
    return {
        "ph": {"type": "number", "required": True, "min": 2.5, "max": 4.5},
        "alcohol": {"type": "number", "required": True, "min": 8.0, "max": 15.0},
        "quality": {"type": "number", "required": True, "min": 0, "max": 10},
        "total_sulfur_dioxide": {"type": "number", "required": False},
        "free_sulfur_dioxide": {"type": "number", "required": False},
    }


def test_m3_cross_field_pass_and_fail() -> None:
    body = {
        "version": "2",
        "fields": _wine_like_fields(),
        "rules": ["required", "range_validation", "type_check"],
        "cross_field_rules": [
            {
                "id": "high_alcohol_quality",
                "expression": "quality >= 5 OR alcohol < 12",
                "error_message": "High alcohol needs quality ≥ 5",
                "fields": ["alcohol", "quality"],
            }
        ],
    }
    ok = validate_schema(
        resolved={"ph": 3.5, "alcohol": 11.0, "quality": 6.0},
        schema_body=body,
        evidence_map={},
    )
    assert ok.status == "PASS"
    bad = validate_schema(
        resolved={"ph": 3.5, "alcohol": 13.0, "quality": 4.0},
        schema_body=body,
        evidence_map={},
    )
    assert bad.status == "FAIL"
    assert any(e.rule == "high_alcohol_quality" for e in bad.errors)


def test_m3_cross_field_skipped_when_referenced_value_missing() -> None:
    body = {
        "version": "2",
        "fields": _wine_like_fields(),
        "rules": ["required", "range_validation", "type_check"],
        "cross_field_rules": [
            {
                "id": "high_alcohol_quality",
                "expression": "quality >= 5 OR alcohol < 12",
                "error_message": "msg",
                "fields": ["alcohol", "quality"],
            }
        ],
    }
    rep = validate_schema(
        resolved={"ph": 3.5, "alcohol": 13.0},
        schema_body=body,
        evidence_map={},
    )
    assert rep.status == "FAIL"
    assert any(e.field == "quality" and e.rule == "required" for e in rep.errors)
    assert not any(e.rule == "high_alcohol_quality" for e in rep.errors)


def test_m3_repeating_group_row_fail() -> None:
    body = {
        "version": "2",
        "fields": _wine_like_fields(),
        "rules": ["required", "range_validation", "type_check"],
        "groups": {
            "test_results": {
                "section_hint": "Test Results",
                "structure_hint": "list",
                "row_fields": {
                    "parameter": {"type": "string"},
                    "measured_value": {"type": "number"},
                    "lower_bound": {"type": "number"},
                    "upper_bound": {"type": "number"},
                },
                "row_rules": [
                    {
                        "id": "within_spec",
                        "expression": "lower_bound <= measured_value AND measured_value <= upper_bound",
                        "error_message": "{parameter}: out of range",
                    }
                ],
            }
        },
    }
    blk = TextBlock(
        id="b0",
        page=1,
        bbox=(0, 0, 400, 200),
        text="Test Results\nDilution 105 0 100\nBadLine 200 0 100",
        section_label="Test Results",
    )
    rep = validate_schema(
        resolved={"ph": 3.5, "alcohol": 12.0, "quality": 7.0},
        schema_body=body,
        blocks=[blk],
        evidence_map={},
    )
    assert rep.status == "FAIL"
    assert any("test_results[1]" in e.field for e in rep.errors)
    assert any(e.rule == "within_spec" for e in rep.errors)


def test_m3_schema_version_1_ignores_cross_field_rules() -> None:
    """Without ``version: \"2\"``, cross-field rules are not evaluated (Milestone 3 contract)."""

    body = {
        "version": "1",
        "fields": _wine_like_fields(),
        "rules": ["required", "range_validation", "type_check"],
        "cross_field_rules": [
            {
                "id": "high_alcohol_quality",
                "expression": "quality >= 5 OR alcohol < 12",
                "error_message": "would fail",
                "fields": ["alcohol", "quality"],
            }
        ],
    }
    rep = validate_schema(
        resolved={"ph": 3.5, "alcohol": 13.0, "quality": 4.0},
        schema_body=body,
        evidence_map={},
    )
    assert rep.status == "PASS"


def test_m3_cross_field_sulfur_dioxide_order_pass_and_fail() -> None:
    body = {
        "version": "2",
        "fields": _wine_like_fields(),
        "rules": ["required", "range_validation", "type_check"],
        "cross_field_rules": [
            {
                "id": "sulfur_dioxide_order",
                "expression": "total_sulfur_dioxide >= free_sulfur_dioxide",
                "error_message": "Total ({total_sulfur_dioxide}) vs free ({free_sulfur_dioxide})",
                "fields": ["free_sulfur_dioxide", "total_sulfur_dioxide"],
            }
        ],
    }
    ok = validate_schema(
        resolved={
            "ph": 3.5,
            "alcohol": 12.0,
            "quality": 6.0,
            "total_sulfur_dioxide": 155.0,
            "free_sulfur_dioxide": 46.0,
        },
        schema_body=body,
        evidence_map={},
    )
    assert ok.status == "PASS"
    bad = validate_schema(
        resolved={
            "ph": 3.5,
            "alcohol": 12.0,
            "quality": 6.0,
            "total_sulfur_dioxide": 30.0,
            "free_sulfur_dioxide": 46.0,
        },
        schema_body=body,
        evidence_map={},
    )
    assert bad.status == "FAIL"
    assert any(e.rule == "sulfur_dioxide_order" for e in bad.errors)


def test_m3_repeating_group_three_rows_fail_three_errors() -> None:
    body = {
        "version": "2",
        "fields": _wine_like_fields(),
        "rules": ["required", "range_validation", "type_check"],
        "groups": {
            "test_results": {
                "section_hint": "Test Results",
                "structure_hint": "table",
                "row_fields": {
                    "parameter": {"type": "string"},
                    "measured_value": {"type": "number"},
                    "lower_bound": {"type": "number"},
                    "upper_bound": {"type": "number"},
                },
                "row_rules": [
                    {
                        "id": "within_spec",
                        "expression": "lower_bound <= measured_value AND measured_value <= upper_bound",
                        "error_message": "out",
                    }
                ],
            }
        },
    }
    lines = [
        "Test Results",
        "parameter | measured_value | lower_bound | upper_bound",
        "A | 10 | 0 | 100",
        "B | 200 | 0 | 100",
        "C | 15 | 0 | 10",
        "D | 999 | 0 | 100",
    ]
    blk = TextBlock(id="b0", page=1, bbox=(0, 0, 1, 1), text="\n".join(lines), section_label="Test Results")
    rep = validate_schema(
        resolved={"ph": 3.5, "alcohol": 12.0, "quality": 7.0},
        schema_body=body,
        blocks=[blk],
        evidence_map={},
    )
    assert rep.status == "FAIL"
    bad = [e for e in rep.errors if e.rule == "within_spec"]
    assert len(bad) == 3


def test_m3_repeating_group_not_found() -> None:
    body = {
        "version": "2",
        "fields": _wine_like_fields(),
        "rules": ["required", "range_validation", "type_check"],
        "groups": {
            "test_results": {
                "section_hint": "Missing Section XYZ",
                "row_fields": {
                    "parameter": {"type": "string"},
                    "measured_value": {"type": "number"},
                    "lower_bound": {"type": "number"},
                    "upper_bound": {"type": "number"},
                },
                "row_rules": [],
            }
        },
    }
    blk = TextBlock(
        id="b0",
        page=1,
        bbox=(0, 0, 1, 1),
        text="Wine QA Report\npH: 3.5",
        section_label=None,
    )
    rep = validate_schema(
        resolved={"ph": 3.5, "alcohol": 12.0, "quality": 7.0},
        schema_body=body,
        blocks=[blk],
        evidence_map={},
    )
    assert rep.status == "FAIL"
    assert any(e.rule == "group_not_found" for e in rep.errors)


def test_m3_repeating_group_sections_row_rule_pass() -> None:
    body = {
        "version": "2",
        "fields": _wine_like_fields(),
        "rules": ["required", "range_validation", "type_check"],
        "groups": {
            "lots": {
                "section_hint": "Samples",
                "structure_hint": "sections",
                "row_fields": {
                    "moisture": {"type": "number"},
                    "ash": {"type": "number"},
                },
                "row_rules": [
                    {
                        "id": "ash_small",
                        "expression": "ash <= 0.5",
                        "error_message": "Ash too high",
                    }
                ],
            }
        },
    }
    text = "Samples\n\nLot A\nMoisture: 12\nAsh: 0.1\n\nLot B\nMoisture: 15\nAsh: 0.2"
    blk = TextBlock("b0", 1, (0, 0, 1, 1), text, section_label="Samples")
    rep = validate_schema(
        resolved={"ph": 3.5, "alcohol": 12.0, "quality": 7.0},
        schema_body=body,
        blocks=[blk],
        evidence_map={},
    )
    assert rep.status == "PASS"
