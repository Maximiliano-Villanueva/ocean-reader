"""Deterministic resolution of ensemble extraction candidates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ocean_read.domain.validation.mapping import FieldEntry

# Higher wins; aligns with product priority: regex > layout > LLM fallback.
SOURCE_PRIORITY: dict[str, int] = {
    "regex": 3,
    "layout": 2,
    "llm": 1,
}


@dataclass(frozen=True)
class ExtractionCandidate:
    """One extractor hypothesis for a logical field."""

    field: str
    value: Any
    source: str
    confidence: float
    block_id: str = ""
    page: int = 1
    evidence_text: str = ""
    bbox: tuple[float, float, float, float] | None = None
    section_label: str | None = None


def _block_index(block_id: str) -> int:
    """Document-order index from ``b12`` -> 12 (for deterministic tie-break)."""

    if block_id.startswith("b"):
        suffix = block_id[1:]
        if suffix.isdigit():
            return int(suffix)
    return 10**9


def _sort_key(c: ExtractionCandidate) -> tuple[int, float, int]:
    prio = SOURCE_PRIORITY.get(c.source.lower(), 0)
    return (-prio, -c.confidence, _block_index(c.block_id))


def resolve_field_candidate(field: str, candidates: list[ExtractionCandidate]) -> ExtractionCandidate:
    """Pick exactly one candidate per field — reproducible for identical inputs."""

    same = [c for c in candidates if c.field == field]
    if not same:
        raise ValueError(f"No candidates for field {field!r}")
    ordered = sorted(same, key=_sort_key)
    return ordered[0]


def resolve_field(field: str, candidates: list[ExtractionCandidate]) -> Any:
    """Pick exactly one value per field — reproducible for identical inputs."""

    return resolve_field_candidate(field, candidates).value


def candidate_to_evidence_dict(c: ExtractionCandidate) -> dict[str, Any]:
    """Serialize traceability payload for API / validation errors."""

    out: dict[str, Any] = {
        "text": c.evidence_text or "",
        "block_id": c.block_id,
        "page": c.page,
    }
    if c.bbox is not None:
        out["bbox"] = [float(x) for x in c.bbox]
    if c.section_label is not None:
        out["section_label"] = c.section_label
    return out


def resolve_document_with_evidence(
    candidates: list[ExtractionCandidate],
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """Resolve values plus per-field evidence maps for downstream validation."""

    fields = {c.field for c in candidates}
    resolved: dict[str, Any] = {}
    evidence: dict[str, dict[str, Any]] = {}
    for fname in sorted(fields):
        win = resolve_field_candidate(fname, candidates)
        resolved[fname] = win.value
        evidence[fname] = candidate_to_evidence_dict(win)
    return resolved, evidence


def resolve_from_field_map(
    field_map: dict[str, FieldEntry],
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """Resolve only ``found`` entries; missing and ambiguous are omitted from ``resolved``."""

    resolved: dict[str, Any] = {}
    evidence: dict[str, dict[str, Any]] = {}
    for fname in sorted(field_map.keys()):
        entry = field_map[fname]
        if entry.status != "found":
            continue
        cands = list(entry.candidates)
        win = resolve_field_candidate(fname, cands)
        resolved[fname] = win.value
        evidence[fname] = candidate_to_evidence_dict(win)
    return resolved, evidence


def resolve_document(candidates: list[ExtractionCandidate]) -> dict[str, Any]:
    """Resolve every field present in ``candidates`` (union of field names)."""

    fields = {c.field for c in candidates}
    return {f: resolve_field(f, candidates) for f in sorted(fields)}
