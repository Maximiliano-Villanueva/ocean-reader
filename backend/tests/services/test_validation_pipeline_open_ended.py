"""Pipeline integration: open-ended fields with mocked Ollama."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from ocean_read.domain.validation.pdf_blocks import TextBlock
from ocean_read.services.validation_pipeline import run_wine_pdf_validation

_SCHEMA = {
    "version": "3",
    "fields": {"ph": {"type": "number", "required": True, "min": 2.5, "max": 4.5}},
    "rules": ["required", "range_validation"],
    "open_ended": {
        "summary": {
            "extract_prompt": "Summarize",
            "informative_only": True,
            "link_evidence": False,
        }
    },
}


def _minimal_pdf() -> bytes:
    import fitz

    doc = fitz.open()
    p = doc.new_page()
    p.insert_text((72, 72), "pH: 3.5\nQuality narrative: acceptable batch.")
    out = doc.tobytes()
    doc.close()
    return out


@pytest.mark.asyncio
async def test_pipeline_open_ended_informative_mock_ollama() -> None:
    class FakeOllama:
        async def chat_json(self, system: str, user: str, *, temperature: float = 0.15):
            return {"value": "Batch acceptable", "evidence_quote": None}

        async def aclose(self) -> None:
            pass

    with patch("ocean_read.services.validation_pipeline.OllamaLLMClient", return_value=FakeOllama()):
        rep = await run_wine_pdf_validation(
            _minimal_pdf(),
            schema_body=_SCHEMA,
            schema_key="t",
            version_label="1",
            llm_fallback=False,
            open_ended_enabled=True,
        )
    assert rep.status == "PASS"
    assert len(rep.open_ended_results) == 1
    assert rep.open_ended_results[0].field == "summary"
    assert rep.open_ended_results[0].informative_only is True
