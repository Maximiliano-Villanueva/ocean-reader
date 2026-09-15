"""Invoice fixture corpus: strict + cross-field (LLM off)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ocean_read.services.validation_pipeline import run_wine_pdf_validation

_FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "invoice"


def _load() -> tuple[dict, list]:
    data = json.loads((_FIXTURE / "corpus_index.json").read_text(encoding="utf-8"))
    schema = json.loads((_FIXTURE / data["schema"]).read_text(encoding="utf-8"))
    # Full agent-prompt E2E lives in ``test_invoice_cursor_agent_e2e.py``.
    rows = [r for r in data["rows"] if r.get("id") != "inv_cursor_formatted"]
    return schema, rows


@pytest.fixture
def invoice_schema() -> dict:
    schema, _ = _load()
    return schema


@pytest.mark.asyncio
@pytest.mark.parametrize("row", _load()[1], ids=lambda r: r["id"])
async def test_invoice_corpus_strict(row: dict, invoice_schema: dict) -> None:
    pdf = (_FIXTURE / row["clean_pdf"]).read_bytes()
    rep = await run_wine_pdf_validation(
        pdf,
        schema_body=invoice_schema,
        schema_key="invoice_v3",
        version_label="1.0",
        llm_fallback=False,
        open_ended_enabled=False,
    )
    assert rep.status == row["expected_status"]
    got = {(e.field, e.rule) for e in rep.errors}
    exp = {(e["field"], e["rule"]) for e in row["expected_errors"]}
    assert got == exp
