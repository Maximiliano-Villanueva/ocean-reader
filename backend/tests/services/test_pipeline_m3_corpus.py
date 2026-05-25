"""M3 corpus: ``m3_corpus_index.json`` + ``schema_m3_wine_cross_field.json`` full pipeline."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ocean_read.services.validation_pipeline import run_wine_pdf_validation

_FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "wine"


def _load_m3_corpus() -> dict:
    return json.loads((_FIXTURE_DIR / "m3_corpus_index.json").read_text(encoding="utf-8"))


@pytest.fixture
def m3_schema() -> dict:
    data = _load_m3_corpus()
    rel = data.get("schema") or "schema_m3_wine_cross_field.json"
    return json.loads((_FIXTURE_DIR / rel).read_text(encoding="utf-8"))


@pytest.mark.asyncio
@pytest.mark.parametrize("case", _load_m3_corpus()["rows"], ids=lambda r: r["id"])
async def test_m3_corpus_cross_field_pdf(case: dict, m3_schema: dict) -> None:
    """Cross-field PASS/FAIL on committed synthetic PDFs (see ``generate_fixtures.py --m3-only``)."""

    pdf_path = _FIXTURE_DIR / case["clean_pdf"]
    assert pdf_path.is_file(), f"Run: python backend/tests/fixtures/wine/generate_fixtures.py --m3-only"
    rep = await run_wine_pdf_validation(
        pdf_path.read_bytes(),
        schema_body=m3_schema,
        schema_key="wine_m3_fixture",
        version_label="1.0",
        llm_fallback=False,
    )
    assert rep.status == case["expected_status"]
    got_pairs = {(e.field, e.rule) for e in rep.errors}
    exp_pairs = {(e["field"], e["rule"]) for e in case["expected_errors"]}
    assert exp_pairs == got_pairs, f"errors: expected {exp_pairs}, got {got_pairs}"
