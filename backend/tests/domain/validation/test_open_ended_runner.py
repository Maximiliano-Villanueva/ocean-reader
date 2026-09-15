"""Open-ended runner with mocked vLLM."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from ocean_read.domain.validation.open_ended_runner import run_open_ended_fields
from ocean_read.domain.validation.pdf_blocks import TextBlock


@pytest.mark.asyncio
async def test_open_ended_informative_does_not_change_evaluation() -> None:
    blocks = [
        TextBlock(
            id="b1",
            page=1,
            text="Conclusion: wine quality is acceptable for export.",
            bbox=(72.0, 72.0, 400.0, 90.0),
        )
    ]
    schema = {
        "version": "3",
        "fields": {},
        "rules": [],
        "open_ended": {
            "summary": {
                "extract_prompt": "Summarize the conclusion",
                "informative_only": True,
                "link_evidence": True,
            }
        },
    }
    client = AsyncMock()
    client.chat_json = AsyncMock(return_value={"value": "Acceptable for export", "evidence_quote": "acceptable for export"})
    results = await run_open_ended_fields(
        schema_body=schema,
        blocks=blocks,
        resolved_strict={},
        client=client,
        enabled=True,
    )
    assert len(results) == 1
    assert results[0].informative_only is True
    assert results[0].evaluation is None
    assert results[0].extracted_value == "Acceptable for export"


@pytest.mark.asyncio
async def test_open_ended_evaluated_pass_fail() -> None:
    blocks = [
        TextBlock(
            id="b1",
            page=1,
            text="pH: 3.5 Alcohol: 12% Quality narrative: meets spec.",
            bbox=(72.0, 72.0, 500.0, 90.0),
        )
    ]
    schema = {
        "version": "3",
        "fields": {"ph": {"type": "number"}},
        "rules": [],
        "open_ended": {
            "narrative_check": {
                "extract_prompt": "Extract quality narrative",
                "evaluate_prompt": "Does narrative align with ph 3.5?",
                "depends_on_fields": ["ph"],
                "link_evidence": True,
            }
        },
    }
    class _FakeClient:
        def __init__(self) -> None:
            self.n = 0

        async def chat_json(self, system: str, user: str, *, temperature: float = 0.15):
            self.n += 1
            if self.n == 1:
                return {"value": "meets spec", "evidence_quote": "meets spec"}
            return {"evaluation": "pass", "rationale": "aligned"}

    client = _FakeClient()
    results = await run_open_ended_fields(
        schema_body=schema,
        blocks=blocks,
        resolved_strict={"ph": 3.5},
        client=client,
        enabled=True,
    )
    assert results[0].evaluation == "pass"
