"""
Agent-side schema normalization (mirrors backend ``schema_normalizer`` logic).
"""

from __future__ import annotations

import copy
import re
from typing import Any

_STRICT_FIELD_HINTS: dict[str, dict[str, Any]] = {
    "invoice_number": {
        "aliases": ["Número de factura", "Numero de factura", "Invoice number"],
        "regex_hint": r"(?i)(?:n[uú]mero\s*de\s*factura|invoice\s*number)\s*[:=\s]*([A-Z0-9][A-Z0-9-]{2,})",
        "on_ambiguity": "first",
    },
    "issue_date": {
        "aliases": ["Fecha de emisión", "Fecha de emision", "Issue date"],
        "regex_hint": (
            r"(?i)(?:fecha\s*de\s*emisi[oó]n|issue\s*date)\s*[:=\s]*"
            r"(\d{1,2}\s+de\s+\w+\s+de\s+\d{4}|\d{1,2}[-/]\d{1,2}[-/]\d{2,4})"
        ),
        "llm_fallback": True,
    },
    "invoice_issue_date": {
        "aliases": ["Fecha de emisión", "Fecha de emision", "Issue date"],
        "regex_hint": r"(?i)fecha\s*de\s*emisi[oó]n\s*[:=\s]*(.+?)(?:\n|$)",
        "llm_fallback": True,
    },
    "due_date": {
        "aliases": ["Fecha de vencimiento", "Due date"],
        "regex_hint": (
            r"(?i)(?:fecha\s*de\s*vencimiento|due\s*date)\s*[:=\s]*"
            r"(\d{1,2}\s+de\s+\w+\s+de\s+\d{4}|\d{1,2}[-/]\d{1,2}[-/]\d{2,4})"
        ),
        "llm_fallback": True,
    },
    "invoice_due_date": {
        "aliases": ["Fecha de vencimiento", "Due date"],
        "regex_hint": r"(?i)fecha\s*de\s*vencimiento\s*[:=\s]*(.+?)(?:\n|$)",
        "llm_fallback": True,
    },
    "total_due": {
        "aliases": ["Importe por pagar", "Total due", "Total"],
        "regex_hint": r"(?i)(?:importe\s*por\s*pagar|total\s*due|total)\s*[:=\s]*USD?\s*([\d,.]+)",
    },
    "recipient_email": {
        "aliases": ["Email", "Correo"],
        "regex_hint": r"([\w.+-]+@[\w.-]+\.\w+)",
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

_FIELD_KEY_ALIASES: dict[str, str] = {
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


def _humanize_field_name(name: str) -> str:
    return name.replace("_", " ").strip()


def _should_skip_regex_hint(fname: str, spec: dict[str, Any]) -> bool:
    if spec.get("llm_only"):
        return True
    if fname == "invoice_number" and spec.get("llm_fallback"):
        return True
    if fname == "invoice_number" and spec.get("extraction_hint") and not spec.get("regex_hint"):
        return True
    return False


def _canonicalize_field_keys(body: dict[str, Any]) -> None:
    fields = body.get("fields")
    if not isinstance(fields, dict):
        return
    for alias, canonical in _FIELD_KEY_ALIASES.items():
        if alias not in fields:
            continue
        if canonical in fields:
            del fields[alias]
        else:
            fields[canonical] = fields.pop(alias)


def _repair_open_ended_entries(body: dict[str, Any]) -> None:
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


def normalize_schema_body(body: dict[str, Any]) -> dict[str, Any]:
    """Repair common agent mistakes before DSL validation."""

    out = copy.deepcopy(body)
    if out.get("open_ended"):
        out["version"] = "3"
    if not out.get("rules"):
        out["rules"] = ["required", "range_validation", "type_check"]

    fields = out.get("fields")
    if isinstance(fields, dict):
        oe = out.setdefault("open_ended", {})
        if not isinstance(oe, dict):
            oe = {}
            out["open_ended"] = oe
        remove: list[str] = []
        for name, spec in fields.items():
            if not isinstance(spec, dict):
                continue
            if str(spec.get("type") or "").lower() == "open_ended":
                entry = {k: v for k, v in spec.items() if k != "type"}
                if not entry.get("extract_prompt"):
                    entry["extract_prompt"] = entry.pop("description", "") or f"Extract {name}"
                oe[name] = entry
                remove.append(name)
        for name in remove:
            del fields[name]

        _canonicalize_field_keys(out)

        for fname, spec in list(fields.items()):
            if not isinstance(spec, dict):
                continue
            rules = spec.pop("rules", None)
            if not isinstance(rules, list):
                continue
            for rule in rules:
                if not isinstance(rule, dict) or str(rule.get("rule_name", "")).lower() != "equals":
                    continue
                expected = rule.get("value")
                if spec.get("type") == "number":
                    try:
                        n = float(expected)
                        spec["min"] = spec["max"] = n
                    except (TypeError, ValueError):
                        pass
                elif spec.get("type") == "string" and expected is not None:
                    spec["regex_hint"] = rf"(?i){re.escape(str(expected))}"
            hints = _STRICT_FIELD_HINTS.get(fname)
            if hints:
                if not spec.get("aliases"):
                    spec["aliases"] = list(hints.get("aliases") or [])
                if _should_skip_regex_hint(fname, spec):
                    spec.pop("regex_hint", None)
                    spec["llm_fallback"] = True
                    if not spec.get("extraction_hint"):
                        spec["extraction_hint"] = (
                            "Extract the unique invoice identifier using document context; "
                            "do not rely on a bare alphanumeric pattern."
                        )
                elif not spec.get("regex_hint") and hints.get("regex_hint"):
                    spec["regex_hint"] = hints["regex_hint"]
                if spec.get("llm_fallback") is None and hints.get("llm_fallback"):
                    spec["llm_fallback"] = hints["llm_fallback"]

    _repair_open_ended_entries(out)
    return out
