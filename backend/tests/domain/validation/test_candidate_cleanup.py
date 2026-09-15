"""Candidate deduplication and false-ambiguity reconciliation."""

from __future__ import annotations

from ocean_read.domain.validation.candidate_cleanup import (
    dedupe_extraction_candidates,
    reconcile_field_map,
)
from ocean_read.domain.validation.mapping import FieldEntry
from ocean_read.domain.validation.resolution import ExtractionCandidate


def _c(field: str, value: object, source: str = "regex", block_id: str = "b1") -> ExtractionCandidate:
    return ExtractionCandidate(
        field=field,
        value=value,
        source=source,
        confidence=0.9,
        block_id=block_id,
        page=1,
        evidence_text=str(value),
    )


def test_dedupe_same_field_value_block() -> None:
    a = _c("issue_date", "9 de agosto de 2025", block_id="b2")
    b = _c("issue_date", "9 de agosto de 2025", block_id="b2")
    out = dedupe_extraction_candidates([a, b])
    assert len(out) == 1


def test_reconcile_same_value_not_ambiguous() -> None:
    """Multiple candidates with the same value should collapse to one winner."""

    entry = FieldEntry(
        status="ambiguous",
        candidates=(
            _c("due_date", "9 de agosto de 2025", block_id="b3"),
            _c("due_date", "9 de agosto de 2025", block_id="b23"),
            _c("due_date", "9 de agosto de 2025", block_id="b15"),
        ),
    )
    fm = reconcile_field_map({"due_date": entry}, {"due_date": {"on_ambiguity": "first"}})
    assert fm["due_date"].status == "found"
    assert len(fm["due_date"].candidates) == 1


def test_reconcile_spanish_date_prefix_variants() -> None:
    entry = FieldEntry(
        status="ambiguous",
        candidates=(
            _c("due_date", "9 de agosto de 2025", block_id="b3"),
            _c("due_date", "del 9 de agosto de 2025", source="layout", block_id="b15"),
        ),
    )
    fm = reconcile_field_map({"due_date": entry}, {"due_date": {}})
    assert fm["due_date"].status == "found"


def test_reconcile_invoice_number_strips_glued_suffix() -> None:
    entry = FieldEntry(
        status="ambiguous",
        candidates=(
            _c("invoice_number", "DOEA864B-0011"),
            _c("invoice_number", "DOEA864B-0011Total"),
        ),
    )
    fm = reconcile_field_map({"invoice_number": entry}, {"invoice_number": {"on_ambiguity": "first"}})
    assert fm["invoice_number"].status == "found"
    assert fm["invoice_number"].candidates[0].value == "DOEA864B-0011"
