"""Tests for manual field corrections that create a revalidated run revision."""

from __future__ import annotations

import json
from pathlib import Path

from ocean_read.domain.validation.run_manual_revision import apply_manual_field_corrections

_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "wine"
_SCHEMA = json.loads((_FIXTURES / "schema.json").read_text())


def test_correction_fixes_range_failure_to_pass() -> None:
    """Lowering alcohol into range should flip FAIL → PASS."""

    report = {
        "status": "FAIL",
        "schema_id": "wine_schema",
        "schema_version": "1.0",
        "schema_snapshot": _SCHEMA,
        "resolved_values": {"ph": 3.5, "alcohol": 18.0, "quality": 7},
        "results": [
            {
                "field": "alcohol",
                "value": 18.0,
                "expected": {"min": 8.0, "max": 15.0},
                "rule": "range_validation",
                "evidence": None,
            }
        ],
        "field_rule_outcomes": [
            {"field": "alcohol", "rule": "range_validation", "passed": False, "value": 18.0},
            {"field": "ph", "rule": "required", "passed": True, "value": 3.5},
        ],
        "ambiguous_fields": [],
        "open_ended_results": [],
    }

    updated = apply_manual_field_corrections(report, {"alcohol": 9.4})

    assert updated["status"] == "PASS"
    assert updated["resolved_values"]["alcohol"] == 9.4
    assert updated["results"] == []
    assert any(o["field"] == "alcohol" and o["passed"] for o in updated["field_rule_outcomes"])


def test_correction_clears_ambiguous_field() -> None:
    """Picking a value for an ambiguous field revalidates when no ambiguity remains."""

    report = {
        "status": "AMBIGUOUS",
        "schema_id": "wine_schema",
        "schema_version": "1.0",
        "schema_snapshot": _SCHEMA,
        "resolved_values": {"ph": 3.1, "quality": 7},
        "results": [],
        "field_rule_outcomes": [],
        "ambiguous_fields": [{"field": "alcohol", "candidate_count": 2}],
        "open_ended_results": [],
    }

    updated = apply_manual_field_corrections(report, {"alcohol": 12.0})

    assert updated["status"] == "PASS"
    assert updated["ambiguous_fields"] == []
    assert updated["resolved_values"]["alcohol"] == 12.0


def test_partial_ambiguous_correction_stays_ambiguous() -> None:
    """Correcting one ambiguous field while another remains unresolved keeps AMBIGUOUS."""

    report = {
        "status": "AMBIGUOUS",
        "schema_id": "wine_schema",
        "schema_version": "1.0",
        "schema_snapshot": _SCHEMA,
        "resolved_values": {"quality": 7},
        "results": [],
        "field_rule_outcomes": [],
        "ambiguous_fields": [
            {"field": "alcohol", "candidate_count": 2},
            {"field": "ph", "candidate_count": 2},
        ],
        "open_ended_results": [],
    }

    updated = apply_manual_field_corrections(report, {"alcohol": 12.0})

    assert updated["status"] == "AMBIGUOUS"
    assert len(updated["ambiguous_fields"]) == 1
    assert updated["ambiguous_fields"][0]["field"] == "ph"
