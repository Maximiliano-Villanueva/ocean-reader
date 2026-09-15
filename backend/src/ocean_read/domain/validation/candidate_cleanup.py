"""
Deduplicate extraction candidates and reconcile false ambiguity.

Multiple regex hits for the same labeled value (e.g. Spanish dates) are not real ambiguity.
"""

from __future__ import annotations

import re
from typing import Any

from ocean_read.domain.validation.ambiguity_policy import pick_candidate_by_strategy, parse_on_ambiguity
from ocean_read.domain.validation.mapping import FieldEntry, _values_equivalent
from ocean_read.domain.validation.resolution import ExtractionCandidate, resolve_field_candidate

_INVOICE_ID_RE = re.compile(
    r"^([A-Z0-9]+(?:-\d+)+|[A-Z0-9]{2,}(?:-[A-Z0-9]+)*)",
    re.IGNORECASE,
)
_SPANISH_DATE_FRAGMENT_RE = re.compile(
    r"(\d{1,2}\s+de\s+\w+\s+de\s+\d{4})",
    re.IGNORECASE,
)


def _canonical_value(field: str, value: Any) -> Any:
    """Normalize values so glued PDF text does not create false ambiguity."""

    if value is None:
        return value
    if field == "invoice_number" or ("invoice" in field and "number" in field):
        s = str(value).strip()
        m = _INVOICE_ID_RE.match(s)
        if m:
            return m.group(1)
        glued = re.match(r"^([A-Z0-9]+-\d+)", s, re.IGNORECASE)
        if glued:
            return glued.group(1)
    if isinstance(value, str):
        s = " ".join(value.split())
        if "date" in field.lower() or "fecha" in field.lower():
            m = _SPANISH_DATE_FRAGMENT_RE.search(s)
            if m:
                return m.group(1).lower()
        return s
    return value


def _value_key(field: str, value: Any) -> str:
    canon = _canonical_value(field, value)
    if isinstance(canon, float):
        return f"n:{round(canon, 6)}"
    return f"s:{str(canon).lower()}"


def dedupe_extraction_candidates(candidates: list[ExtractionCandidate]) -> list[ExtractionCandidate]:
    """Drop exact duplicates (field + canonical value + block)."""

    seen: set[tuple[str, str, str]] = set()
    out: list[ExtractionCandidate] = []
    for c in candidates:
        key = (c.field, _value_key(c.field, c.value), c.block_id or "")
        if key in seen:
            continue
        seen.add(key)
        out.append(c)
    return out


def _distinct_canonical_values(field: str, candidates: list[ExtractionCandidate]) -> list[Any]:
    uniq: list[Any] = []
    for c in candidates:
        canon = _canonical_value(field, c.value)
        if not any(_values_equivalent(canon, u) for u in uniq):
            uniq.append(canon)
    return uniq


def reconcile_field_map(
    field_map: dict[str, FieldEntry],
    schema_fields: dict[str, Any],
) -> dict[str, FieldEntry]:
    """
    Collapse duplicate equivalent candidates and resolve false ambiguity.

    True ambiguity (distinct canonical values) is left for ``apply_ambiguity_policies``.
    """

    out: dict[str, FieldEntry] = {}
    for fname, entry in field_map.items():
        spec = schema_fields.get(fname) if isinstance(schema_fields.get(fname), dict) else {}
        cands = list(entry.candidates)
        if not cands:
            out[fname] = entry
            continue

        distinct = _distinct_canonical_values(fname, cands)
        if len(distinct) <= 1:
            strategy = parse_on_ambiguity(spec or {}) or "best_match"
            try:
                winner = pick_candidate_by_strategy(fname, cands, strategy)
            except ValueError:
                winner = resolve_field_candidate(fname, cands)
            canon_val = _canonical_value(fname, winner.value)
            if canon_val != winner.value:
                winner = ExtractionCandidate(
                    field=winner.field,
                    value=canon_val,
                    source=winner.source,
                    confidence=winner.confidence,
                    block_id=winner.block_id,
                    page=winner.page,
                    evidence_text=winner.evidence_text,
                    bbox=winner.bbox,
                    section_label=winner.section_label,
                )
            out[fname] = FieldEntry(status="found", candidates=(winner,))
            continue

        if entry.status == "found" and len(cands) > 1:
            winner = resolve_field_candidate(fname, cands)
            out[fname] = FieldEntry(status="found", candidates=(winner,))
            continue

        out[fname] = entry
    return out
