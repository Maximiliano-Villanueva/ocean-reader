"""Apply a persisted schema ``body`` to resolved field values — deterministic PASS/FAIL."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_NUMERIC_EPS = 0.001
# Slacks only near boundaries so ``min``/``max`` stay inclusive without widening the band.
_RANGE_BOUND_SLACK = 1e-9

_RULE_SORT = {"required": 0, "type_check": 1, "range_validation": 2}


@dataclass(frozen=True)
class FieldValidationError:
    field: str
    value: Any
    expected: Any
    rule: str
    evidence: dict[str, Any] | None


@dataclass(frozen=True)
class FieldRuleOutcome:
    """One check of a single global rule against one field (pass or fail)."""

    field: str
    rule: str
    passed: bool
    value: Any | None = None
    expected: Any | None = None
    evidence: dict[str, Any] | None = None


@dataclass(frozen=True)
class ValidationReport:
    """Result of schema validation (Stages 7–8); ``status`` is PASS or FAIL only.

    ``AMBIGUOUS`` is assigned by the pipeline when inconsistency is detected **before**
    this function runs; see :func:`validate_schema`.

    ``outcomes`` lists every rule–field check executed (for audit / UI), including passes.
    """

    schema_key: str | None
    schema_version: str | None
    status: str  # PASS | FAIL
    errors: tuple[FieldValidationError, ...]
    outcomes: tuple[FieldRuleOutcome, ...]


def _coerce_number(v: Any) -> float | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    return None


def validate_schema(
    *,
    resolved: dict[str, Any],
    schema_body: dict[str, Any],
    schema_key: str | None = None,
    version_label: str | None = None,
    evidence_map: dict[str, dict[str, Any]] | None = None,
) -> ValidationReport:
    """Validate resolved values against the schema DSL (min/max, required, type_check).

    Supported global ``rules`` entries in ``schema_body``:

    - ``required``: for each field with ``"required": true``, the key must exist in ``resolved``.
    - ``range_validation``: for ``number`` fields with ``min`` / ``max``.
    - ``type_check``: for fields with ``type``, ensure value is coercible to that type.

    Field specs use ``min`` / ``max`` (not ``range``).
    """

    fields_spec = schema_body.get("fields") or {}
    rules = list(schema_body.get("rules") or [])
    errors: list[FieldValidationError] = []
    outcomes: list[FieldRuleOutcome] = []
    ev = evidence_map or {}

    if "required" in rules:
        for fname, spec in fields_spec.items():
            if not isinstance(spec, dict):
                continue
            if not spec.get("required"):
                continue
            if fname not in resolved:
                errors.append(
                    FieldValidationError(
                        field=fname,
                        value=None,
                        expected="present",
                        rule="required",
                        evidence=ev.get(fname),
                    )
                )
                outcomes.append(
                    FieldRuleOutcome(
                        field=fname,
                        rule="required",
                        passed=False,
                        value=None,
                        expected="present",
                        evidence=ev.get(fname),
                    )
                )
            else:
                outcomes.append(
                    FieldRuleOutcome(
                        field=fname,
                        rule="required",
                        passed=True,
                        value=resolved[fname],
                        expected="present",
                        evidence=ev.get(fname),
                    )
                )

    if "type_check" in rules:
        for fname, spec in fields_spec.items():
            if fname not in resolved:
                continue
            if not isinstance(spec, dict):
                continue
            typ = spec.get("type")
            if typ == "number":
                raw = resolved[fname]
                if _coerce_number(raw) is None:
                    errors.append(
                        FieldValidationError(
                            field=fname,
                            value=raw,
                            expected="number",
                            rule="type_check",
                            evidence=ev.get(fname),
                        )
                    )
                    outcomes.append(
                        FieldRuleOutcome(
                            field=fname,
                            rule="type_check",
                            passed=False,
                            value=raw,
                            expected="number",
                            evidence=ev.get(fname),
                        )
                    )
                else:
                    outcomes.append(
                        FieldRuleOutcome(
                            field=fname,
                            rule="type_check",
                            passed=True,
                            value=raw,
                            expected="number",
                            evidence=ev.get(fname),
                        )
                    )

    if "range_validation" in rules:
        for fname, spec in fields_spec.items():
            if fname not in resolved:
                continue
            if not isinstance(spec, dict):
                continue
            if spec.get("type") != "number":
                continue
            raw = resolved[fname]
            num = _coerce_number(raw)
            if num is None:
                continue
            min_v = spec.get("min")
            max_v = spec.get("max")
            low = float(min_v) if min_v is not None else None
            high = float(max_v) if max_v is not None else None
            if low is None and high is None:
                continue
            pair_low = low if low is not None else float("-inf")
            pair_high = high if high is not None else float("inf")
            below_min = low is not None and num + _RANGE_BOUND_SLACK < float(low)
            above_max = high is not None and num - _RANGE_BOUND_SLACK > float(high)
            if below_min or above_max:
                expected: Any = []
                if low is not None:
                    expected.append(low)
                if high is not None:
                    expected.append(high)
                if len(expected) == 2:
                    exp_out: Any = [expected[0], expected[1]]
                elif len(expected) == 1:
                    exp_out = expected[0]
                else:
                    exp_out = [pair_low, pair_high]
                errors.append(
                    FieldValidationError(
                        field=fname,
                        value=num,
                        expected=exp_out,
                        rule="range_validation",
                        evidence=ev.get(fname),
                    )
                )
                outcomes.append(
                    FieldRuleOutcome(
                        field=fname,
                        rule="range_validation",
                        passed=False,
                        value=num,
                        expected=exp_out,
                        evidence=ev.get(fname),
                    )
                )
            else:
                exp_ok: Any = []
                if low is not None:
                    exp_ok.append(low)
                if high is not None:
                    exp_ok.append(high)
                if len(exp_ok) == 2:
                    exp_display: Any = [exp_ok[0], exp_ok[1]]
                elif len(exp_ok) == 1:
                    exp_display = exp_ok[0]
                else:
                    exp_display = None
                outcomes.append(
                    FieldRuleOutcome(
                        field=fname,
                        rule="range_validation",
                        passed=True,
                        value=num,
                        expected=exp_display,
                        evidence=ev.get(fname),
                    )
                )

    outcomes.sort(key=lambda o: (o.field, _RULE_SORT.get(o.rule, 9)))

    status = "PASS" if not errors else "FAIL"
    return ValidationReport(
        schema_key=schema_key,
        schema_version=version_label,
        status=status,
        errors=tuple(errors),
        outcomes=tuple(outcomes),
    )


def validate_wine_style_schema(
    *,
    resolved: dict[str, Any],
    schema_body: dict[str, Any],
    schema_key: str | None = None,
    version_label: str | None = None,
    evidence_map: dict[str, dict[str, Any]] | None = None,
) -> ValidationReport:
    """Backward-compatible alias for :func:`validate_schema`."""

    return validate_schema(
        resolved=resolved,
        schema_body=schema_body,
        schema_key=schema_key,
        version_label=version_label,
        evidence_map=evidence_map,
    )
