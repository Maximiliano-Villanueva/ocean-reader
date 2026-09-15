"""Tests for per-field ``on_ambiguity`` resolution."""

from __future__ import annotations

from ocean_read.domain.validation.ambiguity_policy import (
    apply_ambiguity_policies,
    parse_on_ambiguity,
    pick_candidate_by_strategy,
)
from ocean_read.domain.validation.mapping import FieldEntry
from ocean_read.domain.validation.resolution import ExtractionCandidate


def _c(field: str, value: object, *, block_id: str, source: str = "regex") -> ExtractionCandidate:
    return ExtractionCandidate(
        field=field,
        value=value,
        source=source,
        confidence=0.9 if source == "regex" else 0.5,
        block_id=block_id,
        page=1,
    )


def test_parse_on_ambiguity_aliases() -> None:
    assert parse_on_ambiguity({"on_ambiguity": "first-value"}) == "first"
    assert parse_on_ambiguity({"on_ambiguity": "last-value"}) == "last"
    assert parse_on_ambiguity({}) is None


def test_pick_first_uses_document_order() -> None:
    cands = [
        _c("invoice_number", "B", block_id="b10"),
        _c("invoice_number", "A", block_id="b2"),
    ]
    win = pick_candidate_by_strategy("invoice_number", cands, "first")
    assert win.value == "A"


def test_pick_last_uses_document_order() -> None:
    cands = [
        _c("invoice_number", "A", block_id="b2"),
        _c("invoice_number", "B", block_id="b10"),
    ]
    win = pick_candidate_by_strategy("invoice_number", cands, "last")
    assert win.value == "B"


def test_apply_ambiguity_policies_resolves_configured_field() -> None:
    entry = FieldEntry(
        status="ambiguous",
        candidates=(
            _c("invoice_number", "X", block_id="b1"),
            _c("invoice_number", "Y", block_id="b2"),
        ),
    )
    field_map = {"invoice_number": entry, "total": FieldEntry(status="missing", candidates=())}
    schema = {"invoice_number": {"on_ambiguity": "first"}, "total": {}}
    out = apply_ambiguity_policies(field_map, schema)
    assert out["invoice_number"].status == "found"
    assert out["invoice_number"].candidates[0].value == "X"
    assert out["total"].status == "missing"
