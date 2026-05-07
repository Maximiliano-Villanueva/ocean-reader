"""Schema mapping and inconsistency detection (TC-UNIT-030–034)."""

from __future__ import annotations

import pytest

from ocean_read.domain.validation.mapping import (
    check_inconsistencies,
    map_candidates_to_schema,
    unmatched_schema_candidates,
)
from ocean_read.domain.validation.resolution import ExtractionCandidate


def test_tc_unit_030_found_single_candidate() -> None:
    fields = {"ph": {"type": "number"}}
    c = [ExtractionCandidate("ph", 3.4, "regex", 0.9, block_id="b0")]
    m = map_candidates_to_schema(c, fields)
    assert m["ph"].status == "found"
    assert len(m["ph"].candidates) == 1


def test_tc_unit_031_missing_field() -> None:
    fields = {"ph": {"type": "number"}, "alcohol": {"type": "number"}}
    c = [ExtractionCandidate("ph", 3.4, "regex", 0.9, block_id="b0")]
    m = map_candidates_to_schema(c, fields)
    assert m["alcohol"].status == "missing"


def test_tc_unit_032_ambiguous_distinct_values() -> None:
    fields = {"ph": {"type": "number"}}
    c = [
        ExtractionCandidate("ph", 3.1, "regex", 0.9, block_id="b0"),
        ExtractionCandidate("ph", 4.2, "regex", 0.9, block_id="b1"),
    ]
    m = map_candidates_to_schema(c, fields)
    assert m["ph"].status == "ambiguous"
    inc = check_inconsistencies(m)
    assert inc.has_ambiguity
    assert inc.ambiguous_fields[0].field == "ph"


def test_tc_unit_033_duplicate_same_value_collapses_to_found() -> None:
    fields = {"alcohol": {"type": "number"}}
    c = [
        ExtractionCandidate("alcohol", 12.0, "layout", 0.5, block_id="b0"),
        ExtractionCandidate("alcohol", 12.0, "regex", 0.9, block_id="b1"),
    ]
    m = map_candidates_to_schema(c, fields)
    assert m["alcohol"].status == "found"


def test_tc_unit_034_alias_match_and_extras() -> None:
    fields = {"ph": {"type": "number", "aliases": ["pH level"]}}
    c = [
        ExtractionCandidate("pH level", 3.3, "regex", 0.9, block_id="b0"),
        ExtractionCandidate("unknown_metric", 99.0, "layout", 0.3, block_id="b2"),
    ]
    m = map_candidates_to_schema(c, fields)
    assert m["ph"].status == "found"
    extra = unmatched_schema_candidates(c, fields)
    assert len(extra) == 1
    assert extra[0].field == "unknown_metric"
