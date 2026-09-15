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


def test_layout_wine_ignores_trailing_numbers_on_docling_glued_blob() -> None:
    """Docling often emits one block without newlines; layout must not pick Quality's value for Alcohol."""

    blocks = [
        TextBlock(
            id="b1",
            page=1,
            bbox=(72.0, 64.0, 400.0, 200.0),
            text=(
                "Header · Página 1 de 2 · billing table USD20.00 "
                "SECTION: Chemical Analysis pH: 3.51 Alcohol: 9.4% Quality: 5"
            ),
        ),
    ]
    candidates = ensemble_wine_extractors(blocks)
    resolved, _ = resolve_document_with_evidence(candidates)
    assert resolved["alcohol"] == 9.4
    assert resolved["quality"] == 5.0


def test_regex_wine_emits_all_matches_in_glued_docling_blob() -> None:
    """Duplicate labels in one Docling block must surface as multiple candidates."""

    blocks = [
        TextBlock(
            id="b1",
            page=1,
            bbox=(72.0, 64.0, 400.0, 200.0),
            text="SECTION: Chemical Analysis pH: 3.1 Alcohol: 12% Quality: 7 pH: 4.2",
        ),
    ]
    ph_vals = sorted(c.value for c in ensemble_wine_extractors(blocks) if c.field == "ph" and c.source == "regex")
    assert ph_vals == [3.1, 4.2]
