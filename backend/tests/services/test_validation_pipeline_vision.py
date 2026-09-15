"""Pipeline invokes vision fallback when text extraction leaves required fields missing."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from ocean_read.domain.validation.resolution import ExtractionCandidate
from ocean_read.services.validation_pipeline import run_wine_pdf_validation


@pytest.mark.asyncio
async def test_pipeline_vision_fallback_fills_missing_required() -> None:
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 40, 20), False)
    page.insert_image(fitz.Rect(72, 72, 200, 150), pixmap=pix)
    pdf_bytes = doc.tobytes()
    doc.close()

    schema = {
        "version": "2",
        "fields": {
            "alcohol": {"type": "number", "required": True, "min": 0, "max": 20},
            "quality": {"type": "number", "required": True, "min": 0, "max": 100},
            "ph": {"type": "number", "required": True, "min": 0, "max": 14},
        },
    }
    vision_cands = [
        ExtractionCandidate(field="alcohol", value=11.0, source="vision", confidence=0.42, page=1),
        ExtractionCandidate(field="quality", value=88.0, source="vision", confidence=0.42, page=1),
        ExtractionCandidate(field="ph", value=3.5, source="vision", confidence=0.42, page=1),
    ]

    with patch(
        "ocean_read.services.validation_pipeline.vision_fallback_candidates",
        new_callable=AsyncMock,
        return_value=vision_cands,
    ):
        result = await run_wine_pdf_validation(
            pdf_bytes,
            schema_body=schema,
            schema_key="wine",
            version_label="1.0",
            llm_fallback=False,
            llm_vision=True,
        )

    assert result.pipeline_snapshots is not None
    assert result.pipeline_snapshots.get("extraction_meta", {}).get("vision_fallback_used") is True
    assert any(c.get("source") == "vision" for c in result.pipeline_snapshots.get("candidates", []))
