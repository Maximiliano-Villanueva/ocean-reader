"""PDF → pipeline regression using Wine Quality schema fixture (no LLM)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ocean_read.services.validation_pipeline import run_wine_pdf_validation

_FIXTURE_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "wine"


@pytest.fixture
def wine_schema() -> dict:
    return json.loads((_FIXTURE_DIR / "schema.json").read_text(encoding="utf-8"))


def _wine_report_pdf(*, alcohol_line: str) -> bytes:
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    y = 72
    for line in ("Wine QA Report", "pH: 3.5", alcohol_line, "Quality: 7"):
        page.insert_text((72, y), line)
        y += 18
    out = doc.tobytes()
    doc.close()
    return out


@pytest.mark.asyncio
async def test_pipeline_fail_out_of_range_alcohol(wine_schema: dict) -> None:
    pdf = _wine_report_pdf(alcohol_line="Alcohol: 18%")
    rep = await run_wine_pdf_validation(
        pdf,
        schema_body=wine_schema,
        schema_key="wine_schema",
        version_label="1.0",
        llm_fallback=False,
    )
    assert rep.status == "FAIL"
    alc_err = next(e for e in rep.errors if e.field == "alcohol")
    assert alc_err.rule == "range_validation"
    assert alc_err.evidence is not None
    assert alc_err.evidence.get("page") == 1
    assert "Alcohol" in (alc_err.evidence.get("text") or "")


@pytest.mark.asyncio
async def test_pipeline_pass_wine_sample(wine_schema: dict) -> None:
    pdf = _wine_report_pdf(alcohol_line="Alcohol: 12%")
    rep = await run_wine_pdf_validation(
        pdf,
        schema_body=wine_schema,
        schema_key="wine_schema",
        version_label="1.0",
        llm_fallback=False,
    )
    assert rep.status == "PASS"
    assert not rep.errors
