"""Ensemble extractors + resolution over synthetic blocks."""

from __future__ import annotations

from ocean_read.domain.validation.extractors_wine import ensemble_wine_extractors
from ocean_read.domain.validation.pdf_blocks import TextBlock
from ocean_read.domain.validation.resolution import resolve_document_with_evidence


def test_ensemble_resolves_wine_fields_with_evidence() -> None:
    blocks = [
        TextBlock(
            id="b0",
            page=2,
            bbox=(10.0, 10.0, 100.0, 40.0),
            text="pH: 3.5\nAlcohol: 18%\nQuality: 7",
        ),
    ]
    candidates = ensemble_wine_extractors(blocks)
    resolved, evidence = resolve_document_with_evidence(candidates)
    assert resolved["ph"] == 3.5
    assert resolved["alcohol"] == 18.0
    assert resolved["quality"] == 7.0
    assert evidence["alcohol"]["block_id"] == "b0"
    assert evidence["alcohol"]["page"] == 2
    assert "bbox" in evidence["alcohol"]
