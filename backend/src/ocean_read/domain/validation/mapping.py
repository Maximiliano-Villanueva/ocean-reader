"""Schema mapping (Stage 3) and inconsistency detection (Stage 5)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from ocean_read.domain.validation.resolution import ExtractionCandidate

_NUMERIC_EPS = 0.001


@dataclass(frozen=True)
class FieldEntry:
    status: Literal["found", "missing", "ambiguous"]
    candidates: tuple[ExtractionCandidate, ...]


@dataclass(frozen=True)
class AmbiguousFieldInfo:
    field: str
    count: int
    candidates: tuple[ExtractionCandidate, ...]


@dataclass(frozen=True)
class InconsistencyReport:
    has_ambiguity: bool
    ambiguous_fields: tuple[AmbiguousFieldInfo, ...]


def normalize_field_name(name: str) -> str:
    return name.lower().replace(" ", "_").replace("-", "_").strip()


def _values_equivalent(a: Any, b: Any) -> bool:
    na = _coerce_float(a)
    nb = _coerce_float(b)
    if na is not None and nb is not None:
        return abs(na - nb) <= _NUMERIC_EPS
    return a == b


def _coerce_float(v: Any) -> float | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    return None


def _candidate_maps_to_schema_field(
    candidate_field: str,
    schema_field: str,
    spec: dict[str, Any],
) -> bool:
    if normalize_field_name(candidate_field) == normalize_field_name(schema_field):
        return True
    aliases = spec.get("aliases") or []
    for a in aliases:
        if candidate_field == a or normalize_field_name(str(a)) == normalize_field_name(candidate_field):
            return True
    return False


def map_candidates_to_schema(
    candidates: list[ExtractionCandidate],
    schema_fields: dict[str, Any],
) -> dict[str, FieldEntry]:
    """Group candidates by schema field; classify each as found, missing, or ambiguous."""

    # Build schema_key -> list of candidates
    per_schema: dict[str, list[ExtractionCandidate]] = {k: [] for k in schema_fields}
    for skey in schema_fields:
        for c in candidates:
            spec = schema_fields[skey] if isinstance(schema_fields[skey], dict) else {}
            if not isinstance(spec, dict):
                spec = {}
            if _candidate_maps_to_schema_field(c.field, skey, spec):
                per_schema[skey].append(c)

    out: dict[str, FieldEntry] = {}
    for skey, cands in per_schema.items():
        if not cands:
            out[skey] = FieldEntry(status="missing", candidates=())
            continue
        # Distinct values
        unique_vals: list[Any] = []
        for c in cands:
            if not any(_values_equivalent(c.value, u) for u in unique_vals):
                unique_vals.append(c.value)
        if len(unique_vals) > 1:
            out[skey] = FieldEntry(status="ambiguous", candidates=tuple(cands))
        else:
            out[skey] = FieldEntry(status="found", candidates=tuple(cands))
    return out


def check_inconsistencies(field_map: dict[str, FieldEntry]) -> InconsistencyReport:
    """Surface fields with status ``ambiguous``."""

    amb: list[AmbiguousFieldInfo] = []
    for fname, entry in field_map.items():
        if entry.status == "ambiguous":
            amb.append(
                AmbiguousFieldInfo(
                    field=fname,
                    count=len(entry.candidates),
                    candidates=entry.candidates,
                )
            )
    return InconsistencyReport(has_ambiguity=bool(amb), ambiguous_fields=tuple(amb))


def unmatched_schema_candidates(
    candidates: list[ExtractionCandidate],
    schema_fields: dict[str, Any],
) -> list[ExtractionCandidate]:
    """Candidates whose ``field`` does not map to any schema key (including aliases)."""

    out: list[ExtractionCandidate] = []
    for c in candidates:
        matched = any(
            _candidate_maps_to_schema_field(c.field, sk, schema_fields[sk] if isinstance(schema_fields[sk], dict) else {})
            for sk in schema_fields
        )
        if not matched:
            out.append(c)
    return out
