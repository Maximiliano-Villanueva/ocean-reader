"""
Mandatory E2E: agent prompt → schema → validation of ``inv_cursor_formatted.pdf``.

Uses mocked Ollama for deterministic CI; contextual extraction is always on in the pipeline.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from ocean_read.domain.validation.document_context import DocumentContext, DocumentRegion
from ocean_read.domain.validation.open_ended_runner import OpenEndedFieldResult
from ocean_read.domain.validation.pdf_blocks import parse_pdf_blocks
from ocean_read.domain.validation.resolution import ExtractionCandidate
from ocean_read.domain.validation.schema_dsl import collect_schema_dsl_errors
from ocean_read.domain.validation.schema_normalizer import normalize_schema_body
from ocean_read.services.validation_pipeline import run_wine_pdf_validation

_FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "invoice"
_REPO_ROOT = Path(__file__).resolve().parents[4]


def _load_agent_prompt_module():
    path = _FIXTURE / "agent_prompt_schema.py"
    spec = importlib.util.spec_from_file_location("agent_prompt_schema", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_agent = _load_agent_prompt_module()
INV_CURSOR_AGENT_USER_PROMPT = _agent.INV_CURSOR_AGENT_USER_PROMPT
INV_CURSOR_OPEN_ENDED_TRUTH = _agent.INV_CURSOR_OPEN_ENDED_TRUTH
INV_CURSOR_STRICT_TRUTH = _agent.INV_CURSOR_STRICT_TRUTH
agent_raw_schema_from_prompt = _agent.agent_raw_schema_from_prompt
normalized_inv_cursor_agent_schema = _agent.normalized_inv_cursor_agent_schema

_SCHEMA_PATH = _FIXTURE / "schema_inv_cursor_agent_prompt.json"
_PDF_PATH = _FIXTURE / "inv_cursor_formatted.pdf"


@pytest.fixture
def inv_cursor_schema() -> dict[str, Any]:
    if _SCHEMA_PATH.is_file():
        return normalize_schema_body(json.loads(_SCHEMA_PATH.read_text(encoding="utf-8")))
    return normalized_inv_cursor_agent_schema()


def test_committed_schema_matches_normalizer() -> None:
    """Golden JSON on disk stays aligned with normalizer output."""

    expected = normalized_inv_cursor_agent_schema()
    if _SCHEMA_PATH.is_file():
        on_disk = normalize_schema_body(json.loads(_SCHEMA_PATH.read_text(encoding="utf-8")))
        assert on_disk == expected
    errs = collect_schema_dsl_errors(expected)
    assert errs == []


@pytest.mark.asyncio
async def test_schema_agent_mocked_ollama_builds_valid_schema() -> None:
    """Schema agent path: user prompt → normalize → valid DSL."""

    raw = agent_raw_schema_from_prompt()
    reply = (
        "Added invoice fields per your request.\n\n"
        f"```schema\n{json.dumps(raw, indent=2)}\n```"
    )

    sys.path.insert(0, str(_REPO_ROOT / "schema_agent" / "src"))

    def _local_validate(body: dict) -> dict:
        errs = collect_schema_dsl_errors(normalize_schema_body(body))
        return {"ok": not errs, "errors": errs}

    with (
        patch("schema_agent.agent_runner.ollama_chat", new_callable=AsyncMock) as mock_chat,
        patch("schema_agent.agent_runner.validate_schema_body", side_effect=_local_validate),
    ):
        mock_chat.return_value = reply
        from schema_agent.agent_runner import SchemaAgentRunner

        runner = SchemaAgentRunner()
        out = await runner.chat(
            messages=[{"role": "user", "content": INV_CURSOR_AGENT_USER_PROMPT}],
            schema_body={"fields": {}, "rules": []},
        )

    body = normalize_schema_body(out["schema_body"])
    assert collect_schema_dsl_errors(body) == []
    assert "recipient_email" in body.get("fields", {})
    assert "recipient_name" in body.get("open_ended", {})
    assert body.get("extraction", {}).get("understand_document") is not False


def _context_for_invoice(blocks: list) -> DocumentContext:
    recipient_ids = [b.id for b in blocks if "facturar" in (b.text or "").lower()][:4]
    issuer_ids = [b.id for b in blocks if "cursor" in (b.text or "").lower()][:2]
    return DocumentContext(
        document_type="invoice",
        summary="SaaS invoice with issuer column and bill-to recipient column",
        regions=(
            DocumentRegion("issuer", tuple(issuer_ids), "Seller / Cursor"),
            DocumentRegion("recipient", tuple(recipient_ids), "Facturar a / bill-to"),
            DocumentRegion("payment_summary", tuple(recipient_ids[-1:] if recipient_ids else ()), "Totals"),
        ),
        disambiguation_notes=(
            "Amount due is Importe por pagar / Total due, not line-item unit price alone.",
            "Recipient is under Facturar a, not the Cursor sender column.",
        ),
    )


def _strict_candidates(blocks: list) -> list[ExtractionCandidate]:
    index = {b.id: b for b in blocks}
    anchor = blocks[0]

    def _c(field: str, value: Any, block_id: str | None = None) -> ExtractionCandidate:
        b = index.get(block_id or "", anchor)
        return ExtractionCandidate(
            field=field,
            value=value,
            source="llm_context",
            confidence=0.9,
            block_id=b.id,
            page=b.page,
            evidence_text=str(value)[:200],
            bbox=b.bbox,
            section_label=b.section_label,
        )

    recip_block = next((b.id for b in blocks if "facturar" in (b.text or "").lower()), anchor.id)
    return [
        _c("invoice_number", INV_CURSOR_STRICT_TRUTH["invoice_number"], recip_block),
        _c("recipient_email", INV_CURSOR_STRICT_TRUTH["recipient_email"], recip_block),
        _c("issue_date", INV_CURSOR_STRICT_TRUTH["issue_date"], recip_block),
        _c("due_date", INV_CURSOR_STRICT_TRUTH["due_date"], recip_block),
        _c("total_due", INV_CURSOR_STRICT_TRUTH["total_due"], recip_block),
    ]


def _open_ended_results() -> tuple[OpenEndedFieldResult, ...]:
    return (
        OpenEndedFieldResult(
            field="recipient_name",
            extracted_value=INV_CURSOR_OPEN_ENDED_TRUTH["recipient_name"],
            evaluation=None,
            informative_only=True,
            evidence=(),
        ),
        OpenEndedFieldResult(
            field="recipient_address",
            extracted_value=INV_CURSOR_OPEN_ENDED_TRUTH["recipient_address"],
            evaluation=None,
            informative_only=True,
            evidence=(),
        ),
    )


@pytest.mark.asyncio
async def test_inv_cursor_formatted_full_extraction_e2e(inv_cursor_schema: dict[str, Any]) -> None:
    """
    End-to-end validation of ``inv_cursor_formatted.pdf`` with agent-prompt schema.

    Contextual extraction is enabled (pipeline default). LLM is mocked to return
  layout-aware values matching the fixture PDF.
    """

    pdf = _PDF_PATH.read_bytes()
    blocks = parse_pdf_blocks(pdf)
    fields_spec = inv_cursor_schema.get("fields") or {}

    async def _fake_infer(
        blocks_in: list,
        *,
        client,
        schema_field_summary: str = "",
        document_text: str | None = None,
    ):  # noqa: ANN001
        return _context_for_invoice(blocks_in)

    async def _fake_extract(
        blocks_in: list,
        fields_spec_in: dict,
        field_names: list[str],
        context: DocumentContext,
        *,
        client,
        document_text: str | None = None,
    ) -> list[ExtractionCandidate]:  # noqa: ANN001
        all_c = _strict_candidates(blocks_in)
        return [c for c in all_c if c.field in field_names]

    with (
        patch(
            "ocean_read.services.validation_contextual.infer_document_context",
            side_effect=_fake_infer,
        ),
        patch(
            "ocean_read.services.validation_contextual.contextual_extract_fields",
            side_effect=_fake_extract,
        ),
        patch(
            "ocean_read.services.validation_pipeline.run_open_ended_fields",
            new_callable=AsyncMock,
            return_value=_open_ended_results(),
        ),
    ):
        rep = await run_wine_pdf_validation(
            pdf,
            schema_body=inv_cursor_schema,
            schema_key="invoice",
            version_label="1.0",
            open_ended_enabled=True,
        )

    assert rep.status == "PASS", f"errors={rep.errors} ambiguous={rep.ambiguous_fields}"
    assert rep.resolved_values is not None
    for key, expected in INV_CURSOR_STRICT_TRUTH.items():
        assert key in rep.resolved_values, f"missing resolved {key}"
        got = rep.resolved_values[key]
        if isinstance(expected, float):
            assert float(got) == pytest.approx(expected)
        else:
            assert expected.lower() in str(got).lower()

    oe_by_field = {r.field: r.extracted_value for r in rep.open_ended_results}
    for field, needle in INV_CURSOR_OPEN_ENDED_TRUTH.items():
        assert field in oe_by_field
        assert needle.lower() in (oe_by_field[field] or "").lower()

    # Contextual LLM may be skipped when reconcile collapses duplicate regex hits to one value per field.
    meta = rep.pipeline_snapshots.get("extraction_meta", {})
    assert meta.get("vision_fallback_used") is False
