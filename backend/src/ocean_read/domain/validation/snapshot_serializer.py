"""Serialize intermediate pipeline state for immutable JSONB persistence (M2 audit trail).

Snapshots capture blocks, extraction candidates, schema field mapping, ambiguity report,
and resolved field values so historic runs remain explainable after code changes.
"""

from __future__ import annotations

from typing import Any

from ocean_read.domain.validation.mapping import (
    AmbiguousFieldInfo,
    FieldEntry,
    InconsistencyReport,
)
from ocean_read.domain.validation.pdf_blocks import TextBlock
from ocean_read.domain.validation.resolution import ExtractionCandidate


def _json_safe(obj: Any) -> Any:
    """Normalize values for JSON round-trip (tuples → lists)."""

    if obj is None:
        return None
    if isinstance(obj, tuple):
        return [_json_safe(x) for x in obj]
    if isinstance(obj, list):
        return [_json_safe(x) for x in obj]
    if isinstance(obj, dict):
        return {str(k): _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (str, int, float, bool)):
        return obj
    # Fallback for Decimal etc.
    return obj


def _block_to_dict(b: TextBlock) -> dict[str, Any]:
    return {
        "id": b.id,
        "page": b.page,
        "bbox": _json_safe(b.bbox),
        "text": b.text,
        "section_label": b.section_label,
        "font_size_max": b.font_size_max,
    }


def _candidate_to_dict(c: ExtractionCandidate) -> dict[str, Any]:
    out: dict[str, Any] = {
        "field": c.field,
        "value": _json_safe(c.value),
        "source": c.source,
        "confidence": c.confidence,
        "block_id": c.block_id,
        "page": c.page,
        "evidence_text": c.evidence_text,
    }
    if c.bbox is not None:
        out["bbox"] = _json_safe(c.bbox)
    if c.section_label is not None:
        out["section_label"] = c.section_label
    return out


def _field_entry_to_dict(entry: FieldEntry) -> dict[str, Any]:
    return {
        "status": entry.status,
        "candidates": [_candidate_to_dict(c) for c in entry.candidates],
    }


def _ambiguous_info_to_dict(info: AmbiguousFieldInfo) -> dict[str, Any]:
    return {
        "field": info.field,
        "count": info.count,
        "candidates": [_candidate_to_dict(c) for c in info.candidates],
    }


def _inconsistency_to_dict(inc: InconsistencyReport) -> dict[str, Any]:
    return {
        "has_ambiguity": inc.has_ambiguity,
        "ambiguous_fields": [_ambiguous_info_to_dict(a) for a in inc.ambiguous_fields],
    }


def serialize_pipeline_snapshots(
    *,
    blocks: list[TextBlock],
    candidates: list[ExtractionCandidate],
    field_map: dict[str, FieldEntry],
    inconsistency: InconsistencyReport,
    resolved_document: dict[str, Any],
    extraction_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a JSON-serializable dict for ``validation_runs.snapshots``."""

    ordered_field_map = {k: _field_entry_to_dict(field_map[k]) for k in sorted(field_map.keys())}
    out: dict[str, Any] = {
        "blocks": [_block_to_dict(b) for b in blocks],
        "candidates": [_candidate_to_dict(c) for c in candidates],
        "field_candidate_map": ordered_field_map,
        "inconsistency_report": _inconsistency_to_dict(inconsistency),
        "resolved_document": _json_safe(resolved_document),
    }
    if extraction_meta:
        out["extraction_meta"] = _json_safe(extraction_meta)
    return out


def deserialize_pipeline_snapshots(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Normalize a decoded JSON snapshot (optional no-op pass for future validation).

    Callers receive the same key structure produced by :func:`serialize_pipeline_snapshots`.
    """

    if raw is None:
        return {}
    return dict(raw)
