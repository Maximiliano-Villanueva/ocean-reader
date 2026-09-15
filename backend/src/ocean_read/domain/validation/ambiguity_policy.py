"""
Per-field ambiguity resolution strategies (schema ``on_ambiguity``).

When multiple distinct extracted values map to one strict field, the default pipeline
status is ``ambiguous``. Schemas may set ``on_ambiguity`` to pick one candidate deterministically
instead of surfacing AMBIGUOUS for that field.
"""

from __future__ import annotations

from typing import Any, Literal

from ocean_read.domain.validation.mapping import FieldEntry
from ocean_read.domain.validation.resolution import (
    ExtractionCandidate,
    resolve_field_candidate,
)

AmbiguityStrategy = Literal["best_match", "first", "last", "highest_confidence", "any"]

_VALID_STRATEGIES: frozenset[str] = frozenset(
    {"best_match", "first", "last", "highest_confidence", "any", "first-value", "last-value"}
)

_ALIASES: dict[str, AmbiguityStrategy] = {
    "first-value": "first",
    "last-value": "last",
}


def parse_on_ambiguity(spec: dict[str, Any]) -> AmbiguityStrategy | None:
    """Return normalized strategy from a field spec, or ``None`` to keep AMBIGUOUS."""

    raw = spec.get("on_ambiguity")
    if raw is None or raw == "":
        return None
    key = str(raw).strip().lower().replace(" ", "_")
    if key not in _VALID_STRATEGIES:
        return None
    return _ALIASES.get(key, key)  # type: ignore[return-value]


def _block_index(block_id: str) -> int:
    if block_id.startswith("b") and block_id[1:].isdigit():
        return int(block_id[1:])
    return 10**9


def _document_order(candidates: list[ExtractionCandidate]) -> list[ExtractionCandidate]:
    """Sort by page then block id (``b12`` → 12)."""

    def key(c: ExtractionCandidate) -> tuple[int, int]:
        page = c.page if c.page > 0 else 1
        return (page, _block_index(c.block_id))

    return sorted(candidates, key=key)


def pick_candidate_by_strategy(
    field: str,
    candidates: list[ExtractionCandidate],
    strategy: AmbiguityStrategy,
) -> ExtractionCandidate:
    """Choose one candidate using the schema strategy (deterministic)."""

    if not candidates:
        raise ValueError(f"No candidates for field {field!r}")
    if strategy == "best_match":
        return resolve_field_candidate(field, candidates)
    if strategy == "highest_confidence":
        return min(
            candidates,
            key=lambda c: (-c.confidence, c.page if c.page > 0 else 1, _block_index(c.block_id)),
        )
    ordered = _document_order(candidates)
    if strategy in {"first", "any"}:
        return ordered[0]
    if strategy == "last":
        return ordered[-1]
    return resolve_field_candidate(field, candidates)


def apply_ambiguity_policies(
    field_map: dict[str, FieldEntry],
    schema_fields: dict[str, Any],
) -> dict[str, FieldEntry]:
    """Collapse ``ambiguous`` entries to ``found`` when ``on_ambiguity`` is set on the field."""

    out: dict[str, FieldEntry] = {}
    for fname, entry in field_map.items():
        if entry.status != "ambiguous":
            out[fname] = entry
            continue
        spec = schema_fields.get(fname) if isinstance(schema_fields.get(fname), dict) else {}
        strategy = parse_on_ambiguity(spec or {})
        if strategy is None:
            out[fname] = entry
            continue
        winner = pick_candidate_by_strategy(fname, list(entry.candidates), strategy)
        out[fname] = FieldEntry(status="found", candidates=(winner,))
    return out
