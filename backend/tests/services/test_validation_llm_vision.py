"""Vision LLM fallback helpers and candidate shaping."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from ocean_read.domain.validation.mapping import FieldEntry, map_candidates_to_schema
from ocean_read.domain.validation.resolution import ExtractionCandidate
from ocean_read.services.validation_llm_vision import (
    extraction_failure_on_fail,
    missing_required_field_names,
    vision_fallback_candidates,
)


def test_missing_required_field_names() -> None:
    field_map = {
        "alcohol": FieldEntry(status="missing", candidates=()),
        "quality": FieldEntry(status="found", candidates=()),
    }
    schema = {
        "alcohol": {"type": "number", "required": True},
        "quality": {"type": "number", "required": False},
    }
    assert missing_required_field_names(field_map, schema) == ["alcohol"]


def test_extraction_failure_on_fail_required_rule() -> None:
    from ocean_read.domain.validation.outcomes import FieldValidationError

    err = FieldValidationError(
        field="alcohol", value=None, expected=True, rule="required", evidence=None
    )
    assert extraction_failure_on_fail((err,), {}, {"alcohol": {}}) is True


@pytest.mark.asyncio
async def test_vision_fallback_candidates_merges_ollama_json() -> None:
    pdf = b"%PDF-1.4 minimal"
    schema = {"alcohol": {"type": "number", "required": True}}
    mock_cands = [
        ExtractionCandidate(
            field="alcohol",
            value=12.5,
            source="vision",
            confidence=0.42,
            block_id="vision-p1",
            page=1,
        )
    ]
    with patch(
        "ocean_read.services.validation_llm_vision.extract_fields_via_ollama_vision",
        new_callable=AsyncMock,
        return_value=mock_cands,
    ):
        out = await vision_fallback_candidates(pdf, schema)
    assert len(out) == 1
    assert out[0].source == "vision"
    fm = map_candidates_to_schema(out, schema)
    assert fm["alcohol"].status == "found"
