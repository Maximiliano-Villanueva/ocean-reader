"""M3: pipeline honors ``cross_field_rules`` after single-field checks."""

from __future__ import annotations

import json
from pathlib import Path

import fitz
import pytest

from ocean_read.services.validation_pipeline import run_wine_pdf_validation

_FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "wine"


@pytest.fixture
def wine_schema_base() -> dict:
    return json.loads((_FIXTURE_DIR / "schema.json").read_text(encoding="utf-8"))


def _pdf_bytes(lines: list[str]) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    y = 72.0
    for line in lines:
        page.insert_text((72.0, y), line)
        y += 18.0
    out = doc.tobytes()
    doc.close()
    return out


@pytest.mark.asyncio
async def test_pipeline_m3_cross_field_fail_on_high_alcohol_low_quality(wine_schema_base: dict) -> None:
    body = {
        **wine_schema_base,
        "version": "2",
        "cross_field_rules": [
            {
                "id": "high_alcohol_quality",
                "expression": "quality >= 5 OR alcohol < 12",
                "error_message": "High alcohol requires quality ≥ 5",
                "fields": ["alcohol", "quality"],
            }
        ],
    }
    pdf = _pdf_bytes(["Wine QA Report", "pH: 3.5", "Alcohol: 13%", "Quality: 4"])
    rep = await run_wine_pdf_validation(
        pdf,
        schema_body=body,
        schema_key="wine_schema",
        version_label="1.0",
        llm_fallback=False,
    )
    assert rep.status == "FAIL"
    assert any(e.rule == "high_alcohol_quality" for e in rep.errors)


@pytest.mark.asyncio
async def test_pipeline_m3_fixture_schema_pass_basic_pdf() -> None:
    """Regression: bundled M3 wine schema (cross-field rules) validates a simple lab PDF."""

    body = json.loads((_FIXTURE_DIR / "schema_m3_wine_cross_field.json").read_text(encoding="utf-8"))
    pdf = _pdf_bytes(["Wine QA Report", "pH: 3.5", "Alcohol: 11%", "Quality: 6"])
    rep = await run_wine_pdf_validation(
        pdf,
        schema_body=body,
        schema_key="wine_m3_fixture",
        version_label="1.0",
        llm_fallback=False,
    )
    assert rep.status == "PASS"


@pytest.mark.asyncio
async def test_pipeline_m3_fixture_schema_fail_high_alcohol_low_quality() -> None:
    body = json.loads((_FIXTURE_DIR / "schema_m3_wine_cross_field.json").read_text(encoding="utf-8"))
    pdf = _pdf_bytes(["Wine QA Report", "pH: 3.5", "Alcohol: 13%", "Quality: 4"])
    rep = await run_wine_pdf_validation(
        pdf,
        schema_body=body,
        schema_key="wine_m3_fixture",
        version_label="1.0",
        llm_fallback=False,
    )
    assert rep.status == "FAIL"
    assert any(e.rule == "high_alcohol_quality" for e in rep.errors)


@pytest.mark.asyncio
async def test_pipeline_m3_repeating_group_list_row_fail_on_pdf(wine_schema_base: dict) -> None:
    """Full PDF parse → extract list rows → row rule FAIL (not only ``TextBlock`` unit tests)."""

    body = {
        **wine_schema_base,
        "version": "2",
        "groups": {
            "test_results": {
                "section_hint": "Test Results",
                "structure_hint": "list",
                "row_fields": {
                    "parameter": {"type": "string"},
                    "measured_value": {"type": "number"},
                    "lower_bound": {"type": "number"},
                    "upper_bound": {"type": "number"},
                },
                "row_rules": [
                    {
                        "id": "within_spec",
                        "expression": "lower_bound <= measured_value AND measured_value <= upper_bound",
                        "error_message": "{parameter}: out of range",
                    }
                ],
            }
        },
    }
    pdf = _pdf_bytes(
        [
            "Wine QA Report",
            "pH: 3.5",
            "Alcohol: 12%",
            "Quality: 7",
            "Test Results",
            "GoodRow 10 0 100",
            "BadRow 200 0 100",
        ],
    )
    rep = await run_wine_pdf_validation(
        pdf,
        schema_body=body,
        schema_key="wine_schema",
        version_label="1.0",
        llm_fallback=False,
    )
    assert rep.status == "FAIL"
    assert any(e.rule == "within_spec" and "test_results[1]" in e.field for e in rep.errors)
