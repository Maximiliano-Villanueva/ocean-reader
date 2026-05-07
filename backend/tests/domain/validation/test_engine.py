"""Rule engine (TC-UNIT-053–056) + schema fixture regression."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ocean_read.domain.validation.engine import validate_schema

_FIXTURE_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "wine"


@pytest.fixture
def wine_schema() -> dict:
    return json.loads((_FIXTURE_DIR / "schema.json").read_text(encoding="utf-8"))


def test_tc_unit_053_boundary_inclusive_pass(wine_schema: dict) -> None:
    """TC-UNIT-053: min/max boundaries are inclusive (within numeric epsilon)."""

    rep = validate_schema(
        resolved={"ph": 2.5, "alcohol": 10.0, "quality": 5},
        schema_body=wine_schema,
    )
    assert rep.status == "PASS"
    assert len(rep.outcomes) == 9
    assert all(o.passed for o in rep.outcomes)


def test_tc_unit_054_just_outside_boundary_fail(wine_schema: dict) -> None:
    """TC-UNIT-054: value epsilon-above max fails ``range_validation``."""

    rep = validate_schema(
        resolved={"ph": 4.5001, "alcohol": 12.0, "quality": 5},
        schema_body=wine_schema,
    )
    assert rep.status == "FAIL"
    assert any(e.field == "ph" and e.rule == "range_validation" for e in rep.errors)


def test_tc_unit_055_multi_error_no_short_circuit(wine_schema: dict) -> None:
    """TC-UNIT-055: engine collects multiple independent rule violations."""

    rep = validate_schema(
        resolved={"ph": 2.0, "alcohol": 20.0},
        schema_body=wine_schema,
    )
    assert rep.status == "FAIL"
    rules_by_field = {(e.field, e.rule) for e in rep.errors}
    assert ("quality", "required") in rules_by_field
    assert len(rep.errors) >= 2


def test_tc_unit_056_type_check_non_numeric(wine_schema: dict) -> None:
    """TC-UNIT-056: non-numeric value for ``number`` field fails ``type_check``."""

    rep = validate_schema(
        resolved={"ph": "not-a-number", "alcohol": 12.0, "quality": 5},
        schema_body=wine_schema,
    )
    assert any(e.field == "ph" and e.rule == "type_check" for e in rep.errors)


def test_engine_pass_and_range_fail(wine_schema: dict) -> None:
    """Regression: in-range sample passes; out-of-range alcohol fails."""

    ok = validate_schema(
        resolved={"ph": 3.5, "alcohol": 12.0, "quality": 6},
        schema_body=wine_schema,
    )
    assert ok.status == "PASS"
    bad = validate_schema(
        resolved={"ph": 3.5, "alcohol": 18.0, "quality": 6},
        schema_body=wine_schema,
    )
    assert bad.status == "FAIL"
    assert any(e.field == "alcohol" for e in bad.errors)


def test_missing_required_quality(wine_schema: dict) -> None:
    rep = validate_schema(
        resolved={"ph": 3.5, "alcohol": 12.0},
        schema_body=wine_schema,
    )
    assert rep.status == "FAIL"
    assert any(e.field == "quality" and e.rule == "required" for e in rep.errors)
