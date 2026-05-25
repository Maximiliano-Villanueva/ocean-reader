"""Regression: corpus manifest drives full pipeline (TC-INTG-003 + TC-INTG-004–007)."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from ocean_read.services.validation_pipeline import run_wine_pdf_validation

_FIXTURE_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "wine"


def _load_corpus() -> dict:
    return json.loads((_FIXTURE_DIR / "corpus_index.json").read_text(encoding="utf-8"))


@pytest.fixture
def wine_schema() -> dict:
    return json.loads((_FIXTURE_DIR / "schema.json").read_text(encoding="utf-8"))


def _corpus_case_ids() -> Iterator[pytest.ParameterSet]:
    data = _load_corpus()
    for row in data["rows"]:
        for variant in ("clean", "noisy"):
            key = f"{variant}_pdf"
            if row.get(key):
                sid = f"{row['id']}_{variant}"
                yield pytest.param(row, variant, id=sid)


@pytest.mark.asyncio
@pytest.mark.parametrize("case,variant", list(_corpus_case_ids()))
async def test_corpus_row_expected_status(case: dict, variant: str, wine_schema: dict) -> None:
    rel = case[f"{variant}_pdf"]
    pdf_path = _FIXTURE_DIR / rel
    assert pdf_path.is_file(), f"Run generate_fixtures.py to create {pdf_path}"
    pdf_bytes = pdf_path.read_bytes()
    report = await run_wine_pdf_validation(
        pdf_bytes,
        schema_body=wine_schema,
        schema_key="wine_schema",
        version_label="1.0",
        llm_fallback=False,
    )
    assert report.status == case["expected_status"]
    exp_errs = case["expected_errors"]
    got_pairs = {(e.field, e.rule) for e in report.errors}
    exp_pairs = {(e["field"], e["rule"]) for e in exp_errs}
    assert exp_pairs == got_pairs, f"Errors mismatch: expected {exp_pairs}, got {got_pairs}"
    amb_exp = case.get("expected_ambiguous_fields")
    if amb_exp is not None:
        got_amb = {a.field for a in report.ambiguous_fields}
        assert got_amb == set(amb_exp), f"Ambiguous fields: expected {set(amb_exp)}, got {got_amb}"
    elif case["expected_status"] == "AMBIGUOUS":
        assert {a.field for a in report.ambiguous_fields}, "AMBIGUOUS status requires at least one ambiguous field"


@pytest.mark.asyncio
@pytest.mark.parametrize("row", _load_corpus()["rows"], ids=lambda r: r["id"])
async def test_tc_intg_004_noisy_same_status_as_clean(row: dict, wine_schema: dict) -> None:
    """TC-INTG-004: noisy variant yields same validation status as clean."""

    if not row.get("noisy_pdf"):
        return
    clean = await run_wine_pdf_validation(
        (_FIXTURE_DIR / row["clean_pdf"]).read_bytes(),
        schema_body=wine_schema,
        schema_key="wine_schema",
        version_label="1.0",
        llm_fallback=False,
    )
    noisy = await run_wine_pdf_validation(
        (_FIXTURE_DIR / row["noisy_pdf"]).read_bytes(),
        schema_body=wine_schema,
        schema_key="wine_schema",
        version_label="1.0",
        llm_fallback=False,
    )
    assert clean.status == noisy.status


@pytest.mark.asyncio
async def test_tc_intg_005_ambiguous_ph(wine_schema: dict) -> None:
    """TC-INTG-005: two conflicting pH extractions → AMBIGUOUS."""

    import fitz

    doc = fitz.open()
    page = doc.new_page()
    y = 72.0
    for line in ("Wine QA", "pH: 3.1", "pH: 4.2", "Alcohol: 12%", "Quality: 7"):
        page.insert_text((72.0, y), line)
        y += 18.0
    pdf = doc.tobytes()
    doc.close()
    rep = await run_wine_pdf_validation(
        pdf,
        schema_body=wine_schema,
        schema_key="wine_schema",
        version_label="1.0",
        llm_fallback=False,
    )
    assert rep.status == "AMBIGUOUS"
    assert any(a.field == "ph" for a in rep.ambiguous_fields)


@pytest.mark.asyncio
async def test_tc_intg_006_determinism(wine_schema: dict) -> None:
    """TC-INTG-006: identical PDF processed three times → identical outcome."""

    pdf = (_FIXTURE_DIR / "clean" / "row_000_clean.pdf").read_bytes()
    outs: list[tuple[str, tuple[tuple[str, str], ...]]] = []
    for _ in range(3):
        rep = await run_wine_pdf_validation(
            pdf,
            schema_body=wine_schema,
            schema_key="wine_schema",
            version_label="1.0",
            llm_fallback=False,
        )
        outs.append((rep.status, tuple((e.field, e.rule) for e in rep.errors)))
    assert outs[0] == outs[1] == outs[2]


@pytest.mark.asyncio
async def test_tc_intg_007_fail_non_required_errors_have_evidence(wine_schema: dict) -> None:
    """TC-INTG-007: on FAIL, every error except ``required`` includes evidence payload."""

    pdf = (_FIXTURE_DIR / "clean" / "row_005_clean.pdf").read_bytes()
    rep = await run_wine_pdf_validation(
        pdf,
        schema_body=wine_schema,
        schema_key="wine_schema",
        version_label="1.0",
        llm_fallback=False,
    )
    assert rep.status == "FAIL"
    for e in rep.errors:
        if e.rule == "required":
            continue
        assert e.evidence is not None
