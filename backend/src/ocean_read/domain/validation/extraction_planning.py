"""
Decide when the pipeline runs document-understanding + contextual LLM extraction.
"""

from __future__ import annotations

from typing import Any

from ocean_read.domain.validation.mapping import FieldEntry
from ocean_read.domain.validation.resolution import ExtractionCandidate


def schema_extraction_config(schema_body: dict[str, Any]) -> dict[str, Any]:
    """Normalized ``extraction`` section from the schema body."""

    ext = schema_body.get("extraction")
    if not isinstance(ext, dict):
        return {"context_pass": "when_needed", "understand_document": True, "read_images": False}
    return {
        "context_pass": str(ext.get("context_pass") or "when_needed"),
        "understand_document": ext.get("understand_document", True) is not False,
        "read_images": ext.get("read_images", False) is True,
    }


def _candidate_count(candidates: list[ExtractionCandidate], field: str) -> int:
    return sum(1 for c in candidates if c.field == field)


def fields_needing_contextual_extraction(
    field_map: dict[str, FieldEntry],
    fields_spec: dict[str, Any],
    candidates: list[ExtractionCandidate],
    schema_body: dict[str, Any],
) -> list[str]:
    """
    Field names that benefit from layout-aware LLM extraction.

    ``context_pass``: ``never`` | ``when_needed`` (default) | ``always``.
    """

    cfg = schema_extraction_config(schema_body)
    if not cfg.get("understand_document", True):
        return []
    mode = str(cfg.get("context_pass") or "when_needed").lower()
    if mode == "never":
        return []

    names: set[str] = set()
    for fname, spec in (fields_spec or {}).items():
        if not isinstance(spec, dict):
            continue
        if mode == "always":
            names.add(str(fname))
            continue
        entry = field_map.get(fname)
        if entry is None:
            names.add(str(fname))
            continue
        if entry.status in ("missing", "ambiguous"):
            names.add(str(fname))
            continue
        if entry.status == "found" and len(entry.candidates) == 1:
            sole = entry.candidates[0]
            if sole.source == "regex" and sole.confidence >= 0.85:
                continue
        if _candidate_count(candidates, str(fname)) > 1:
            names.add(str(fname))
            continue
        role = str(spec.get("semantic_role") or "").lower()
        if role:
            names.add(str(fname))
    return sorted(names)
