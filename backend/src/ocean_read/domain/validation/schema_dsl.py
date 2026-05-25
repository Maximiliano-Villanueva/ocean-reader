"""Validate persisted schema ``body`` DSL including M3 ``cross_field_rules`` and ``groups``."""

from __future__ import annotations

from typing import Any

from ocean_read.domain.validation.expression_evaluator import (
    ExpressionEvaluationError,
    expression_identifiers,
)


def collect_schema_dsl_errors(body: dict[str, Any]) -> list[str]:
    """Return human-readable issues (empty list = OK). Used by API before persisting a version."""

    errs: list[str] = []
    fields = body.get("fields") or {}
    if not isinstance(fields, dict):
        return ["`fields` must be an object"]

    has_m3_features = bool(body.get("cross_field_rules")) or bool(body.get("groups"))
    if has_m3_features and str(body.get("version") or "") != "2":
        errs.append('Milestone 3: set `"version": "2"` when using `cross_field_rules` or `groups`.')

    for cf in body.get("cross_field_rules") or []:
        if not isinstance(cf, dict):
            errs.append("Each `cross_field_rules` entry must be an object")
            continue
        rid = cf.get("id", "?")
        expr = cf.get("expression")
        if not expr or not isinstance(expr, str):
            errs.append(f"cross_field_rules[{rid!r}]: `expression` is required")
            continue
        try:
            idents = expression_identifiers(expr)
        except ExpressionEvaluationError as exc:
            errs.append(f"cross_field_rules[{rid!r}]: invalid expression: {exc}")
            continue
        for name in idents:
            if name not in fields:
                errs.append(f"cross_field_rules[{rid!r}]: unknown field {name!r} in expression")
        fl = cf.get("fields")
        if fl is not None:
            if not isinstance(fl, list):
                errs.append(f"cross_field_rules[{rid!r}]: `fields` must be a list")
            else:
                for name in fl:
                    if str(name) not in fields:
                        errs.append(f"cross_field_rules[{rid!r}]: `fields` lists unknown {name!r}")

    groups = body.get("groups") or {}
    if isinstance(groups, dict):
        for gname, gspec in groups.items():
            if not isinstance(gspec, dict):
                errs.append(f"groups[{gname!r}]: must be an object")
                continue
            if not str(gspec.get("section_hint") or "").strip():
                errs.append(f"groups[{gname!r}]: `section_hint` is required")
            rf = gspec.get("row_fields") or {}
            if not isinstance(rf, dict) or not rf:
                errs.append(f"groups[{gname!r}]: `row_fields` must be a non-empty object")
                continue
            sh = str(gspec.get("structure_hint") or "").strip().lower()
            if sh and sh not in ("table", "list", "sections"):
                errs.append(
                    f"groups[{gname!r}]: `structure_hint` must be one of table, list, sections (got {sh!r})"
                )
            for rr in gspec.get("row_rules") or []:
                if not isinstance(rr, dict):
                    errs.append(f"groups[{gname!r}]: each row_rules entry must be an object")
                    continue
                rrid = rr.get("id", "?")
                rex = rr.get("expression")
                if not rex or not isinstance(rex, str):
                    errs.append(f"groups[{gname!r}] row_rules[{rrid!r}]: `expression` required")
                    continue
                try:
                    ridents = expression_identifiers(rex)
                except ExpressionEvaluationError as exc:
                    errs.append(f"groups[{gname!r}] row_rules[{rrid!r}]: invalid expression: {exc}")
                    continue
                for name in ridents:
                    if name not in rf:
                        errs.append(
                            f"groups[{gname!r}] row_rules[{rrid!r}]: unknown row field {name!r}"
                        )
    elif groups:
        errs.append("`groups` must be an object when present")

    return errs
