"""When contextual extraction should run."""

from __future__ import annotations

from ocean_read.domain.validation.extraction_planning import fields_needing_contextual_extraction
from ocean_read.domain.validation.mapping import FieldEntry
from ocean_read.domain.validation.resolution import ExtractionCandidate


def test_when_needed_includes_missing_and_ambiguous() -> None:
    field_map = {
        "a": FieldEntry(status="missing", candidates=()),
        "b": FieldEntry(
            status="ambiguous",
            candidates=(
                ExtractionCandidate("b", 1, "regex", 0.9, "b1"),
                ExtractionCandidate("b", 2, "regex", 0.9, "b2"),
            ),
        ),
        "c": FieldEntry(status="found", candidates=(ExtractionCandidate("c", 1, "regex", 0.9, "b3"),)),
    }
    names = fields_needing_contextual_extraction(
        field_map,
        {"a": {}, "b": {}, "c": {}},
        [],
        {"extraction": {"context_pass": "when_needed"}},
    )
    assert names == ["a", "b"]


def test_semantic_role_triggers_reextraction() -> None:
    field_map = {
        "recipient_name": FieldEntry(
            status="found",
            candidates=(ExtractionCandidate("recipient_name", "X", "layout", 0.6, "b1"),),
        ),
    }
    names = fields_needing_contextual_extraction(
        field_map,
        {"recipient_name": {"semantic_role": "recipient"}},
        [],
        {},
    )
    assert names == ["recipient_name"]


def test_high_confidence_regex_only_skips_contextual() -> None:
    """Single regex hit should not re-run contextual LLM (avoids duplicate date/email hits)."""

    field_map = {
        "issue_date": FieldEntry(
            status="found",
            candidates=(ExtractionCandidate("issue_date", "9 de agosto de 2025", "regex", 0.9, "b2"),),
        ),
    }
    names = fields_needing_contextual_extraction(
        field_map,
        {"issue_date": {"semantic_role": "issue_date", "type": "date"}},
        [],
        {"extraction": {"context_pass": "when_needed"}},
    )
    assert names == []
