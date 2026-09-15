"""Tests for LLM extraction judge (non-regex resolutions)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from ocean_read.domain.validation.extraction_judge import apply_extraction_judge
from ocean_read.domain.validation.mapping import FieldEntry
from ocean_read.domain.validation.pdf_blocks import TextBlock
from ocean_read.domain.validation.resolution import ExtractionCandidate


@pytest.mark.asyncio
async def test_judge_rejects_llm_keeps_layout_when_same_value() -> None:
    """Rejected LLM pick leaves the remaining layout candidate as found."""

    llm_c = ExtractionCandidate(
        field="total",
        value=20,
        source="llm_context",
        confidence=0.9,
        block_id="b1",
        page=1,
        evidence_text="Total: 20 USD",
    )
    layout_c = ExtractionCandidate(
        field="total",
        value=20,
        source="layout",
        confidence=0.4,
        block_id="b2",
        page=1,
        evidence_text="Total due: 20 USD",
    )
    field_map = {"total": FieldEntry(status="found", candidates=(llm_c, layout_c))}
    schema_fields = {"total": {"type": "number", "required": True, "aliases": ["Total"]}}
    schema_body = {"extraction": {"judge_non_regex": True}}
    blocks = [TextBlock(id="b1", page=1, text="Total: 20 USD", bbox=(0, 0, 1, 1))]

    client = MagicMock()
    client.complete = AsyncMock(return_value='{"approved": false, "reason": "wrong amount"}')

    new_map, notes = await apply_extraction_judge(
        field_map,
        schema_fields,
        schema_body,
        blocks,
        client=client,
        enabled=True,
    )
    assert new_map["total"].status == "found"
    assert len(new_map["total"].candidates) == 1
    assert new_map["total"].candidates[0].source == "layout"  # llm_context winner removed
    assert len(notes) == 1
    assert notes[0].approved is False


@pytest.mark.asyncio
async def test_judge_rejects_only_candidate_marks_missing() -> None:
    """Rejected sole LLM candidate becomes missing."""

    llm_c = ExtractionCandidate(
        field="total",
        value=99,
        source="llm_context",
        confidence=0.5,
        block_id="b1",
        page=1,
        evidence_text="Total: 99",
    )
    field_map = {"total": FieldEntry(status="found", candidates=(llm_c,))}
    client = MagicMock()
    client.complete = AsyncMock(return_value='{"approved": false, "reason": "not in document"}')

    new_map, notes = await apply_extraction_judge(
        field_map,
        {"total": {"type": "number"}},
        {"extraction": {"judge_non_regex": True}},
        [],
        client=client,
        enabled=True,
    )
    assert new_map["total"].status == "missing"
    assert notes[0].field == "total"


@pytest.mark.asyncio
async def test_judge_skips_regex_winner() -> None:
    """Regex-sourced winners are never sent to the judge."""

    regex_c = ExtractionCandidate(
        field="ph",
        value=3.5,
        source="regex",
        confidence=1.0,
        block_id="b1",
        page=1,
        evidence_text="pH: 3.5",
    )
    field_map = {"ph": FieldEntry(status="found", candidates=(regex_c,))}
    client = MagicMock()
    client.complete = AsyncMock()

    new_map, notes = await apply_extraction_judge(
        field_map,
        {"ph": {"type": "number"}},
        {"extraction": {"judge_non_regex": True}},
        [],
        client=client,
        enabled=True,
    )
    assert new_map["ph"].status == "found"
    assert notes == ()
    client.complete.assert_not_called()
