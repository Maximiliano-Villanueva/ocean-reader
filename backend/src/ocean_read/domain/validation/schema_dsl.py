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

    version_str = str(body.get("version") or "")
    has_m3_features = bool(body.get("cross_field_rules")) or bool(body.get("groups"))
    has_open_ended = bool(body.get("open_ended"))
    if has_m3_features and version_str not in ("2", "3"):
        errs.append(
            'Milestone 3: set `"version": "2"` or `"3"` when using `cross_field_rules` or `groups`.'
        )
    if has_open_ended and version_str != "3":
        errs.append('Open-ended fields require `"version": "3"`.')

    for fname, spec in fields.items():
        if not isinstance(spec, dict):
            continue
        if spec.get("required") and not spec.get("regex_hint") and not spec.get("aliases"):
            errs.append(
                f"fields[{fname!r}]: required strict fields need `aliases` and/or `regex_hint` "
                "or extraction will not find values in the PDF"
            )
        per_field_rules = spec.get("rules")
        if isinstance(per_field_rules, list) and per_field_rules:
            errs.append(
                f"fields[{fname!r}]: per-field `rules` arrays are not supported; "
                "use `min`/`max` for numbers or top-level `cross_field_rules` for expressions"
            )
        oa = spec.get("on_ambiguity")
        if oa is not None and str(oa).strip():
            from ocean_read.domain.validation.ambiguity_policy import _VALID_STRATEGIES

            key = str(oa).strip().lower().replace(" ", "_")
            if key not in _VALID_STRATEGIES:
                errs.append(
                    f"fields[{fname!r}]: on_ambiguity must be one of "
                    "best_match, first, last, highest_confidence, any, first-value, last-value"
                )
        if spec.get("semantic_role") is not None and not str(spec.get("semantic_role") or "").strip():
            errs.append(f"fields[{fname!r}]: semantic_role must be a non-empty string when set")

    ext = body.get("extraction")
    if ext is not None and not isinstance(ext, dict):
        errs.append("`extraction` must be an object")
    elif isinstance(ext, dict):
        cp = str(ext.get("context_pass") or "when_needed").lower()
        if cp not in ("never", "when_needed", "always"):
            errs.append('extraction.context_pass must be "never", "when_needed", or "always"')
        ri = ext.get("read_images")
        if ri is not None and not isinstance(ri, bool):
            errs.append("extraction.read_images must be a boolean")

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

    open_ended = body.get("open_ended")
    if open_ended is not None:
        if not isinstance(open_ended, dict):
            errs.append("`open_ended` must be an object")
        else:
            for fname, spec in open_ended.items():
                if not isinstance(spec, dict):
                    errs.append(f"open_ended[{fname!r}]: must be an object")
                    continue
                if not str(spec.get("extract_prompt") or "").strip():
                    errs.append(f"open_ended[{fname!r}]: `extract_prompt` is required")
                informative = bool(spec.get("informative_only", False))
                evaluate = str(spec.get("evaluate_prompt") or "").strip()
                if not informative and not evaluate:
                    errs.append(
                        f"open_ended[{fname!r}]: non-informative fields need `evaluate_prompt` "
                        "or set `informative_only`: true"
                    )
                link_ev = spec.get("link_evidence")
                if link_ev is not None and not isinstance(link_ev, bool):
                    errs.append(f"open_ended[{fname!r}]: `link_evidence` must be boolean")
                tags = spec.get("evaluation_tags")
                if tags is not None:
                    if not isinstance(tags, list):
                        errs.append(f"open_ended[{fname!r}]: `evaluation_tags` must be a list")
                    else:
                        allowed = {"pass", "fail", "ambiguous"}
                        for t in tags:
                            if str(t).strip().lower() not in allowed:
                                errs.append(
                                    f"open_ended[{fname!r}]: invalid evaluation tag {t!r}; "
                                    f"use {sorted(allowed)}"
                                )
                deps = spec.get("depends_on_fields")
                if deps is not None:
                    if not isinstance(deps, list):
                        errs.append(f"open_ended[{fname!r}]: `depends_on_fields` must be a list")
                    else:
                        for d in deps:
                            if str(d) not in fields:
                                errs.append(
                                    f"open_ended[{fname!r}]: depends_on unknown strict field {d!r}"
                                )

    return errs
