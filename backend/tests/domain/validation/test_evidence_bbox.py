"""Tests for tight evidence bbox refinement via PyMuPDF search."""

from __future__ import annotations

from pathlib import Path

import pytest

from ocean_read.domain.validation.evidence_bbox import (
    refine_extraction_candidate_bboxes,
    tight_bbox_for_needle,
)
from ocean_read.domain.validation.pdf_blocks import parse_pdf_blocks
from ocean_read.domain.validation.resolution import ExtractionCandidate

_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "invoice"
_CURSOR_PDF = _FIXTURES / "inv_cursor_formatted.pdf"


@pytest.mark.skipif(not _CURSOR_PDF.is_file(), reason="invoice fixture missing")
def test_tight_bbox_narrower_than_layout_block_for_invoice_number() -> None:
    data = _CURSOR_PDF.read_bytes()
    blocks = parse_pdf_blocks(data)
    inv_block = next(b for b in blocks if "DOEA864B-0011" in b.text)
    block_area = (inv_block.bbox[2] - inv_block.bbox[0]) * (inv_block.bbox[3] - inv_block.bbox[1])
    tight = tight_bbox_for_needle(
        data,
        page=inv_block.page,
        needle="DOEA864B-0011",
        fallback=inv_block.bbox,
    )
    assert tight is not None
    tight_area = (tight[2] - tight[0]) * (tight[3] - tight[1])
    assert tight_area < block_area * 0.6


def test_refine_candidate_replaces_oversized_bbox() -> None:
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), "Invoice number: INV-2025-42", fontsize=10)
    data = doc.tobytes()
    doc.close()
    blocks = parse_pdf_blocks(data)
    block = blocks[0]
    cand = ExtractionCandidate(
        field="invoice_number",
        value="INV-2025-42",
        source="regex",
        confidence=0.9,
        block_id=block.id,
        page=block.page,
        evidence_text="INV-2025-42",
        bbox=block.bbox,
    )
    refined = refine_extraction_candidate_bboxes(data, [cand])[0]
    assert refined.bbox is not None
    assert refined.bbox != block.bbox
    bw = block.bbox[2] - block.bbox[0]
    rw = refined.bbox[2] - refined.bbox[0]
    assert rw < bw * 0.75
