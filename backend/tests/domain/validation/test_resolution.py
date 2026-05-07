"""Deterministic ensemble resolution (TC-UNIT-042–044)."""

from __future__ import annotations

import pytest

from ocean_read.domain.validation.resolution import (
    ExtractionCandidate,
    candidate_to_evidence_dict,
    resolve_document,
    resolve_field_candidate,
    resolve_field,
)


def test_regex_beats_llm() -> None:
    cands = [
        ExtractionCandidate(field="ph", value=3.5, source="llm", confidence=0.99, block_id="b0"),
        ExtractionCandidate(field="ph", value=3.4, source="regex", confidence=0.95, block_id="b1"),
    ]
    assert resolve_field("ph", cands) == 3.4


def test_higher_confidence_same_source() -> None:
    cands = [
        ExtractionCandidate(field="alcohol", value=11.0, source="regex", confidence=0.8, block_id="b0"),
        ExtractionCandidate(field="alcohol", value=12.0, source="regex", confidence=0.95, block_id="b1"),
    ]
    assert resolve_field("alcohol", cands) == 12.0


def test_resolve_document_stable_order() -> None:
    cands = [
        ExtractionCandidate(field="quality", value=8, source="layout", confidence=0.9, block_id="b0"),
        ExtractionCandidate(field="ph", value=3.5, source="regex", confidence=0.9, block_id="b1"),
    ]

    doc = resolve_document(cands)
    assert doc == {"ph": 3.5, "quality": 8}


def test_tc_unit_042_block_order_tiebreak_integer_suffix() -> None:
    """TC-UNIT-042: same source+confidence → lower ``b{n}`` index wins (b2 before b10)."""

    cands = [
        ExtractionCandidate(field="ph", value=3.0, source="regex", confidence=0.9, block_id="b10"),
        ExtractionCandidate(field="ph", value=3.1, source="regex", confidence=0.9, block_id="b2"),
    ]
    assert resolve_field_candidate("ph", cands).value == 3.1


def test_tc_unit_043_empty_candidates_raises() -> None:
    """TC-UNIT-043: no candidates for field is a hard error."""

    with pytest.raises(ValueError, match="No candidates"):
        resolve_field_candidate("ph", [ExtractionCandidate("alcohol", 1.0, "regex", 0.9, block_id="b0")])


def test_tc_unit_044_evidence_dict_carries_section() -> None:
    """TC-UNIT-044: evidence payload includes optional section label."""

    c = ExtractionCandidate(
        field="ph",
        value=3.2,
        source="regex",
        confidence=0.9,
        block_id="b1",
        page=2,
        evidence_text="pH: 3.2",
        section_label="Lab",
    )
    d = candidate_to_evidence_dict(c)
    assert d["section_label"] == "Lab"
    assert d["page"] == 2
