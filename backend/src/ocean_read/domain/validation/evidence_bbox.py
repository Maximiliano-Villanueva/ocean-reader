"""
Refine extraction candidate bounding boxes to match evidence text (not whole layout blocks).

Uses PyMuPDF ``Page.search_for`` for substring-level geometry.
"""

from __future__ import annotations

import re
from typing import Iterable

from ocean_read.domain.validation.resolution import ExtractionCandidate


def _bbox_area(bbox: tuple[float, float, float, float]) -> float:
    x0, y0, x1, y1 = bbox
    return max(0.0, x1 - x0) * max(0.0, y1 - y0)


def _needle_variants(needle: str, value: object | None) -> list[str]:
    """Search phrases from most specific to shortest useful."""

    out: list[str] = []
    seen: set[str] = set()

    def add(s: str) -> None:
        t = (s or "").strip()
        if len(t) < 2 or t.lower() in seen:
            return
        seen.add(t.lower())
        out.append(t)

    add(needle)
    if value is not None:
        add(str(value))
    # Label:value tail after colon
    if ":" in needle:
        add(needle.split(":")[-1].strip())
    # Numeric formatting variants (4.500,00 vs 4500)
    m = re.search(r"[\d][\d.,]*", needle)
    if m:
        add(m.group(0))

    return out


def tight_bbox_for_needle(
    pdf_bytes: bytes,
    *,
    page: int,
    needle: str,
    value: object | None = None,
    fallback: tuple[float, float, float, float] | None = None,
) -> tuple[float, float, float, float] | None:
    """Return a tight bbox for ``needle`` on ``page``, or ``fallback`` when not found."""

    import fitz  # PyMuPDF — lazy import

    if not pdf_bytes:
        return fallback
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        if page < 1 or page > len(doc):
            return fallback
        pg = doc[page - 1]
        best: tuple[float, float, float, float] | None = None
        best_area = float("inf")
        for variant in _needle_variants(needle, value):
            try:
                rects = pg.search_for(variant)
            except Exception:
                rects = []
            for rect in rects or []:
                bb = (float(rect.x0), float(rect.y0), float(rect.x1), float(rect.y1))
                area = _bbox_area(bb)
                if area > 0 and area < best_area:
                    best_area = area
                    best = bb
        if best is not None:
            return best
        return fallback
    finally:
        doc.close()


def refine_extraction_candidate_bboxes(
    pdf_bytes: bytes,
    candidates: Iterable[ExtractionCandidate],
) -> list[ExtractionCandidate]:
    """Tighten each candidate bbox when evidence/value text appears inside a smaller region."""

    out: list[ExtractionCandidate] = []
    for c in candidates:
        fallback = c.bbox
        if fallback is None:
            out.append(c)
            continue
        needle = (c.evidence_text or "").strip() or (
            str(c.value) if c.value is not None else ""
        )
        tight = tight_bbox_for_needle(
            pdf_bytes,
            page=c.page,
            needle=needle,
            value=c.value,
            fallback=fallback,
        )
        if tight is None:
            out.append(c)
            continue
        # Only accept when meaningfully smaller (avoid noise on already-tight boxes)
        if _bbox_area(tight) < _bbox_area(fallback) * 0.92:
            out.append(
                ExtractionCandidate(
                    field=c.field,
                    value=c.value,
                    source=c.source,
                    confidence=c.confidence,
                    block_id=c.block_id,
                    page=c.page,
                    evidence_text=c.evidence_text,
                    bbox=tight,
                    section_label=c.section_label,
                )
            )
        else:
            out.append(c)
    return out


def refine_field_map_bboxes(
    pdf_bytes: bytes,
    field_map: dict,
) -> dict:
    """Refine all candidates stored in a schema field map (``FieldEntry`` values)."""

    from ocean_read.domain.validation.mapping import FieldEntry

    out: dict = {}
    for key, entry in field_map.items():
        if not isinstance(entry, FieldEntry):
            out[key] = entry
            continue
        refined = tuple(
            refine_extraction_candidate_bboxes(pdf_bytes, list(entry.candidates)),
        )
        out[key] = FieldEntry(status=entry.status, candidates=refined)
    return out
