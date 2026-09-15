"""Revalidate a persisted run after human corrections to extracted field values."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from ocean_read.domain.validation.engine import validate_schema
from ocean_read.domain.validation.outcomes import FieldRuleOutcome, FieldValidationError


def _coerce_correction_value(field_spec: dict[str, Any], raw: Any) -> Any:
    """Coerce user-entered correction to the schema field type when possible."""

    ftype = str(field_spec.get("type") or "string")
    if ftype == "number":
        if isinstance(raw, bool):
            return raw
        if isinstance(raw, (int, float)):
            return float(raw)
        if isinstance(raw, str):
            text = raw.strip()
            if not text:
                return raw
            try:
                return float(text)
            except ValueError:
                return raw
    if ftype == "integer":
        if isinstance(raw, int):
            return raw
        if isinstance(raw, float):
            return int(raw)
        if isinstance(raw, str):
            text = raw.strip()
            if not text:
                return raw
            try:
                return int(float(text))
            except ValueError:
                return raw
    return raw


def _outcome_to_dict(o: FieldRuleOutcome) -> dict[str, Any]:
    return {
        "field": o.field,
        "rule": o.rule,
        "passed": o.passed,
        "value": o.value,
        "expected": o.expected,
        "evidence": o.evidence,
    }


def _error_to_dict(e: FieldValidationError) -> dict[str, Any]:
    return {
        "field": e.field,
        "value": e.value,
        "expected": e.expected,
        "rule": e.rule,
        "evidence": e.evidence,
    }


def apply_manual_field_corrections(
    report: dict[str, Any],
    corrections: dict[str, Any],
) -> dict[str, Any]:
    """Apply human edits and recompute PASS / FAIL / AMBIGUOUS for a stored report payload.

    Returns a new report dict suitable for ``ValidateDocumentResponse`` persistence.
    """

    if not corrections:
        msg = "At least one field correction is required."
        raise ValueError(msg)

    next_report = deepcopy(report)
    schema_body = dict(next_report.get("schema_snapshot") or {})
    fields_spec = dict(schema_body.get("fields") or {})
    resolved = dict(next_report.get("resolved_values") or {})

    correction_log: dict[str, Any] = dict(next_report.get("manual_corrections") or {})
    now = datetime.now(timezone.utc).isoformat()

    for field, raw_val in corrections.items():
        spec = fields_spec.get(field, {})
        if not isinstance(spec, dict):
            spec = {}
        previous = resolved.get(field)
        coerced = _coerce_correction_value(spec, raw_val)
        resolved[field] = coerced
        correction_log[field] = {
            "from": previous,
            "to": coerced,
            "corrected_at": now,
        }

    next_report["manual_corrections"] = correction_log
    next_report["resolved_values"] = resolved

    remaining_amb = [
        a
        for a in next_report.get("ambiguous_fields") or []
        if isinstance(a, dict) and a.get("field") not in corrections
    ]
    next_report["ambiguous_fields"] = remaining_amb

    if remaining_amb:
        next_report["status"] = "AMBIGUOUS"
        next_report["results"] = []
        next_report["field_rule_outcomes"] = []
        return next_report

    schema_key = str(next_report.get("schema_id") or "")
    version_label = str(next_report.get("schema_version") or "")
    validation = validate_schema(
        resolved=resolved,
        schema_body=schema_body,
        schema_key=schema_key or None,
        version_label=version_label or None,
    )

    oe_results = next_report.get("open_ended_results") or []
    status = validation.status
    for oe in oe_results:
        if isinstance(oe, dict) and oe.get("evaluation") == "fail" and not oe.get("informative_only"):
            status = "FAIL"
            break
        if isinstance(oe, dict) and oe.get("evaluation") == "ambiguous" and not oe.get("informative_only"):
            status = "AMBIGUOUS"
            break

    next_report["status"] = status
    next_report["results"] = [_error_to_dict(e) for e in validation.errors]
    next_report["field_rule_outcomes"] = [_outcome_to_dict(o) for o in validation.outcomes]
    return next_report
