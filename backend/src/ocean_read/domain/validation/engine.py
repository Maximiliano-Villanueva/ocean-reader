"""Apply a persisted schema ``body`` to resolved field values — deterministic PASS/FAIL."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ocean_read.domain.validation.expression_evaluator import (
    ExpressionEvaluationError,
    evaluate_boolean_expression,
    expression_identifiers,
    interpolate_field_template,
)
from ocean_read.domain.validation.outcomes import (
    FieldRuleOutcome,
    FieldValidationError,
    ValidationReport,
)
from ocean_read.domain.validation.repeating_groups import validate_repeating_groups

if TYPE_CHECKING:
    from ocean_read.domain.validation.pdf_blocks import TextBlock

_RANGE_BOUND_SLACK = 1e-9

_RULE_SORT = {"required": 0, "type_check": 1, "range_validation": 2, "group_not_found": 5}


def _coerce_number(v: Any) -> float | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    return None


def _milestone3_active(schema_body: dict[str, Any]) -> bool:
    """M3 rules apply only when the schema declares ``version`` ``\"2\"`` (see milestone doc)."""

    return str(schema_body.get("version") or "") == "2"


def validate_schema(
    *,
    resolved: dict[str, Any],
    schema_body: dict[str, Any],
    schema_key: str | None = None,
    version_label: str | None = None,
    evidence_map: dict[str, dict[str, Any]] | None = None,
    blocks: list[TextBlock] | None = None,
) -> ValidationReport:
    """Validate resolved values against the schema DSL (min/max, required, type_check).

    Milestone 3: optional ``cross_field_rules``, ``groups``, and ``version`` — see product docs.
    When ``blocks`` is provided, repeating ``groups`` are validated against extracted rows.

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

    if _milestone3_active(schema_body):
        _apply_cross_field_rules(resolved, schema_body, ev, errors, outcomes)
        ge, go = validate_repeating_groups(blocks or [], schema_body, ev)
        errors.extend(ge)
        outcomes.extend(go)

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
    blocks: list[TextBlock] | None = None,
) -> ValidationReport:
    """Backward-compatible alias for :func:`validate_schema`."""

    return validate_schema(
        resolved=resolved,
        schema_body=schema_body,
        schema_key=schema_key,
        version_label=version_label,
        evidence_map=evidence_map,
        blocks=blocks,
    )


def _apply_cross_field_rules(
    resolved: dict[str, Any],
    schema_body: dict[str, Any],
    ev: dict[str, dict[str, Any]],
    errors: list[FieldValidationError],
    outcomes: list[FieldRuleOutcome],
) -> None:
    """Append cross-field rule errors/outcomes (M3). Skips a rule if any referenced value is missing."""

    cfs = schema_body.get("cross_field_rules") or []
    if not isinstance(cfs, list) or not cfs:
        return
    fields_spec = schema_body.get("fields") or {}
    if not isinstance(fields_spec, dict):
        return

    for cf in cfs:
        if not isinstance(cf, dict):
            continue
        rid = str(cf.get("id") or "cross_field")
        expr = str(cf.get("expression") or "")
        msg_t = str(cf.get("error_message") or f"Cross-field rule {rid} failed")
        declared = [str(x) for x in (cf.get("fields") or []) if x]
        if not expr:
            continue
        try:
            idents = expression_identifiers(expr)
        except ExpressionEvaluationError:
            continue
        if any(i not in resolved for i in idents):
            continue
        binding: dict[str, float] = {}
        skip = False
        for i in idents:
            if i not in fields_spec:
                skip = True
                break
            num = _coerce_number(resolved.get(i))
            if num is None:
                skip = True
                break
            binding[i] = float(num)
        if skip:
            continue
        anchor = declared[0] if declared else (next(iter(idents)) if idents else "cross_field")
        ev_cf = _merge_field_evidence(declared or list(idents), ev)
        try:
            ok = evaluate_boolean_expression(expr, binding)
        except ExpressionEvaluationError:
            ok = False
        interp_values = {k: resolved[k] for k in idents if k in resolved}
        interp = interpolate_field_template(msg_t, interp_values)
        if ok:
            outcomes.append(
                FieldRuleOutcome(
                    field=anchor,
                    rule=rid,
                    passed=True,
                    value=binding,
                    expected=expr,
                    evidence=ev_cf,
                )
            )
        else:
            errors.append(
                FieldValidationError(
                    field=anchor,
                    value=binding,
                    expected=expr,
                    rule=rid,
                    evidence=ev_cf,
                )
            )
            outcomes.append(
                FieldRuleOutcome(
                    field=anchor,
                    rule=rid,
                    passed=False,
                    value=binding,
                    expected=interp,
                    evidence=ev_cf,
                )
            )


def _merge_field_evidence(field_names: list[str], ev: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    by: dict[str, Any] = {}
    for f in field_names:
        if f in ev and ev[f]:
            by[f] = ev[f]
    return {"by_field": by} if by else None
