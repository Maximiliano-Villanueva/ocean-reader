"""
Normalize agent-authored schema bodies before DSL validation and persistence.

Repairs common agent mistakes: open_ended under ``fields``, unsupported per-field ``rules``,
and missing extraction hints for invoice-style documents.
"""

from __future__ import annotations

import copy
import re
from typing import Any

# Extraction hints when the agent omits ``aliases`` / ``regex_hint``.
_STRICT_FIELD_HINTS: dict[str, dict[str, Any]] = {
    "invoice_number": {
        "aliases": ["Número de factura", "Numero de factura", "Invoice number"],
        "regex_hint": (
            r"(?i)(?:n[uú]mero\s*de\s*factura|invoice\s*number)\s*[:=\s]*"
            r"([A-Z0-9]+(?:-[A-Z0-9]+)*)(?=\s|$|[^A-Z0-9-])"
        ),
        "on_ambiguity": "first",
    },
    "issue_date": {
        "aliases": ["Fecha de emisión", "Fecha de emision", "Issue date", "fecha de emisión"],
        "regex_hint": (
            r"(?i)(?:fecha\s*de\s*emisi[oó]n|issue\s*date)\s*[:=\s]*"
            r"(\d{1,2}\s+de\s+\w+\s+de\s+\d{4}|\d{1,2}[-/]\d{1,2}[-/]\d{2,4})"
        ),
        "llm_fallback": True,
    },
    "invoice_issue_date": {
        "aliases": ["Fecha de emisión", "Fecha de emision", "Issue date"],
        "regex_hint": (
            r"(?i)(?:fecha\s*de\s*emisi[oó]n|issue\s*date)\s*[:=\s]*"
            r"(\d{1,2}\s+de\s+\w+\s+de\s+\d{4}|\d{1,2}[-/]\d{1,2}[-/]\d{2,4})"
        ),
        "llm_fallback": True,
    },
    "due_date": {
        "aliases": ["Fecha de vencimiento", "Due date", "fecha de vencimiento"],
        "regex_hint": (
            r"(?i)(?:fecha\s*de\s*vencimiento|due\s*date)\s*[:=\s]*"
            r"(\d{1,2}\s+de\s+\w+\s+de\s+\d{4}|\d{1,2}[-/]\d{1,2}[-/]\d{2,4})"
        ),
        "llm_fallback": True,
    },
    "invoice_due_date": {
        "aliases": ["Fecha de vencimiento", "Due date"],
        "regex_hint": (
            r"(?i)(?:fecha\s*de\s*vencimiento|due\s*date)\s*[:=\s]*"
            r"(\d{1,2}\s+de\s+\w+\s+de\s+\d{4}|\d{1,2}[-/]\d{1,2}[-/]\d{2,4})"
        ),
        "llm_fallback": True,
    },
    "total_due": {
        "aliases": ["Importe por pagar", "Total due", "Amount due", "total a pagar"],
        "regex_hint": r"(?i)(?:importe\s*por\s*pagar|total\s*due|amount\s*due)\s*[:=\s]*USD?\s*([\d,.]+)",
        "extraction_hint": "Use the amount due / importe por pagar line, not line-item subtotals or unit prices.",
    },
    "recipient_email": {
        "aliases": ["Email", "Correo", "correo electrónico"],
        "regex_hint": r"(?i)[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}",
        "extraction_hint": "Bill-to / Facturar a recipient only — ignore issuer contact emails.",
    },
}


_OPEN_ENDED_PROMPT_KEYS = (
    "extract_prompt",
    "description",
    "prompt",
    "extraction_prompt",
    "task",
    "instruction",
)


def _humanize_field_name(name: str) -> str:
    return name.replace("_", " ").strip()


def _repair_open_ended_entries(body: dict[str, Any]) -> None:
    """Fill missing ``extract_prompt`` / ``informative_only`` on top-level ``open_ended`` specs."""

    oe = body.get("open_ended")
    if not isinstance(oe, dict):
        return
    for fname, spec in oe.items():
        if not isinstance(spec, dict):
            continue
        extract = str(spec.get("extract_prompt") or "").strip()
        if not extract:
            for key in _OPEN_ENDED_PROMPT_KEYS[1:]:
                candidate = str(spec.get(key) or "").strip()
                if candidate:
                    extract = candidate
                    break
        if not extract:
            extract = f"Extract the {_humanize_field_name(fname)} from the document."
        spec["extract_prompt"] = extract
        for key in _OPEN_ENDED_PROMPT_KEYS[1:]:
            spec.pop(key, None)

        evaluate = str(spec.get("evaluate_prompt") or "").strip()
        if not evaluate and spec.get("informative_only") is not False:
            spec["informative_only"] = True
        if spec.get("informative_only") and spec.get("link_evidence") is None:
            spec["link_evidence"] = True


def _migrate_open_ended_from_fields(body: dict[str, Any]) -> None:
    """Move ``fields`` entries with ``type: open_ended`` into top-level ``open_ended``."""

    fields = body.get("fields")
    if not isinstance(fields, dict):
        return
    oe = body.setdefault("open_ended", {})
    if not isinstance(oe, dict):
        oe = {}
        body["open_ended"] = oe
    to_remove: list[str] = []
    for name, spec in fields.items():
        if not isinstance(spec, dict):
            continue
        if str(spec.get("type") or "").lower() != "open_ended":
            continue
        entry = {k: v for k, v in spec.items() if k != "type"}
        if not entry.get("extract_prompt"):
            entry["extract_prompt"] = entry.pop("description", None) or f"Extract {name.replace('_', ' ')}"
        oe[name] = entry
        to_remove.append(name)
    for name in to_remove:
        del fields[name]
    if oe:
        body["version"] = "3"


def _convert_per_field_rules(body: dict[str, Any]) -> None:
    """Map unsupported ``rules: [{rule_name: equals}]`` to min/max or cross_field_rules."""

    fields = body.get("fields")
    if not isinstance(fields, dict):
        return
    cross = body.setdefault("cross_field_rules", [])
    if not isinstance(cross, list):
        cross = []
        body["cross_field_rules"] = cross
    for fname, spec in fields.items():
        if not isinstance(spec, dict):
            continue
        rules = spec.pop("rules", None)
        if not isinstance(rules, list):
            continue
        for rule in rules:
            if not isinstance(rule, dict):
                continue
            if str(rule.get("rule_name") or "").lower() != "equals":
                continue
            expected = rule.get("value")
            if spec.get("type") == "number":
                try:
                    num = float(expected)
                    spec["min"] = num
                    spec["max"] = num
                except (TypeError, ValueError):
                    pass
            elif spec.get("type") == "string" and expected is not None:
                spec["regex_hint"] = rf"(?i){re.escape(str(expected))}"


def _regex_hint_is_too_loose(hint: str) -> bool:
    """Bare character-class patterns match everywhere (e.g. ``[A-Z0-9-]+`` on invoice PDFs)."""

    h = hint.strip()
    if not h:
        return False
    if re.search(r"\(\?i\)", h):
        inner = h
    else:
        inner = h
    # Anchored label capture groups are OK.
    if re.search(r"(?:fecha|invoice|n[uú]mero|total|email|@)", inner, re.I):
        return False
    if re.fullmatch(r"\[[^\]]+\]\+?", h) or re.fullmatch(r"\(\?i\)\[[^\]]+\]\+?", h):
        return True
    return False


def _should_skip_regex_hint(fname: str, spec: dict[str, Any]) -> bool:
    """True when extraction should rely on LLM/context instead of injected regex."""

    if spec.get("llm_only"):
        return True
    if fname == "invoice_number" and spec.get("llm_fallback"):
        return True
    if fname == "invoice_number" and spec.get("extraction_hint") and not spec.get("regex_hint"):
        return True
    return False


def _canonicalize_field_keys(body: dict[str, Any]) -> None:
    """Rename common agent field keys to canonical DSL names."""

    fields = body.get("fields")
    if not isinstance(fields, dict):
        return
    aliases_to_canonical: dict[str, str] = {
        "document_total": "total_due",
        "total_amount": "total_due",
        "amount_due": "total_due",
        "date_emision": "issue_date",
        "fecha_emision": "issue_date",
        "date_emission": "issue_date",
        "invoice_issue_date": "issue_date",
        "date_vencimiento": "due_date",
        "fecha_vencimiento": "due_date",
        "invoice_due_date": "due_date",
    }
    for alias, canonical in aliases_to_canonical.items():
        if alias not in fields:
            continue
        if canonical in fields:
            del fields[alias]
        else:
            fields[canonical] = fields.pop(alias)

    cross = body.get("cross_field_rules")
    if isinstance(cross, list):
        for cf in cross:
            if not isinstance(cf, dict):
                continue
            fl = cf.get("fields")
            if isinstance(fl, list):
                cf["fields"] = [aliases_to_canonical.get(str(name), str(name)) for name in fl]
            expr = cf.get("expression")
            if isinstance(expr, str):
                for alias, canonical in aliases_to_canonical.items():
                    expr = re.sub(rf"\b{re.escape(alias)}\b", canonical, expr)
                cf["expression"] = expr


def _ensure_extraction_hints(fields: dict[str, Any]) -> None:
    for fname, spec in fields.items():
        if not isinstance(spec, dict):
            continue
        hints = _STRICT_FIELD_HINTS.get(fname)
        if not hints:
            continue
        if not spec.get("aliases"):
            spec["aliases"] = list(hints.get("aliases") or [])
        skip_regex = _should_skip_regex_hint(fname, spec)
        if skip_regex:
            spec.pop("regex_hint", None)
            spec["llm_fallback"] = True
            if not spec.get("extraction_hint"):
                spec["extraction_hint"] = (
                    "Extract the unique invoice identifier using document context; "
                    "do not rely on a bare alphanumeric pattern."
                )
        else:
            current_hint = str(spec.get("regex_hint") or "").strip()
            if (not current_hint or _regex_hint_is_too_loose(current_hint)) and hints.get("regex_hint"):
                spec["regex_hint"] = hints["regex_hint"]
        if not spec.get("on_ambiguity") and hints.get("on_ambiguity"):
            spec["on_ambiguity"] = hints["on_ambiguity"]
        if spec.get("llm_fallback") is None and hints.get("llm_fallback"):
            spec["llm_fallback"] = hints["llm_fallback"]
        if not spec.get("extraction_hint") and hints.get("extraction_hint"):
            spec["extraction_hint"] = hints["extraction_hint"]


def normalize_schema_body(body: dict[str, Any]) -> dict[str, Any]:
    """Return a repaired copy suitable for DSL validation and the validation pipeline."""

    out = copy.deepcopy(body)
    if not out.get("version") and out.get("open_ended"):
        out["version"] = "3"
    if str(out.get("version") or "") == "3" or out.get("open_ended"):
        out["version"] = "3"
    rules = out.get("rules")
    if not isinstance(rules, list) or not rules:
        out["rules"] = ["required", "range_validation", "type_check"]
    _migrate_open_ended_from_fields(out)
    _repair_open_ended_entries(out)
    _convert_per_field_rules(out)
    fields = out.get("fields")
    if isinstance(fields, dict):
        _canonicalize_field_keys(out)
        _ensure_extraction_hints(fields)
    return out


def schema_has_open_ended(body: dict[str, Any]) -> bool:
    """True when the schema defines at least one open-ended LLM field."""

    oe = body.get("open_ended")
    return isinstance(oe, dict) and len(oe) > 0
