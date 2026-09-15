"""Contextual extraction with mocked Ollama."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from ocean_read.domain.validation.contextual_extraction import contextual_extract_fields
from ocean_read.domain.validation.document_context import DocumentContext, DocumentRegion
from ocean_read.domain.validation.pdf_blocks import TextBlock
from ocean_read.providers.ollama import OllamaLLMClient


@pytest.mark.asyncio
async def test_contextual_extract_uses_block_id_for_evidence() -> None:
    blocks = [
        TextBlock(
            id="b5",
            page=1,
            bbox=(300.0, 40.0, 500.0, 120.0),
            text="Facturar a\nAlex Demo",
        ),
        TextBlock(id="b1", page=1, bbox=(10.0, 40.0, 200.0, 80.0), text="Cursor"),
    ]
    context = DocumentContext(
        document_type="invoice",
        summary="Invoice from Cursor to Alex Demo",
        regions=(
            DocumentRegion("recipient", ("b5",), "Bill-to party"),
            DocumentRegion("issuer", ("b1",), "Seller"),
        ),
    )
    llm_response = {
        "fields": {
            "recipient_name": {
                "value": "Alex Demo",
                "block_id": "b5",
                "evidence_text": "Facturar a Alex Demo",
            }
        }
    }
    client = AsyncMock(spec=OllamaLLMClient)
    client.complete = AsyncMock(return_value=json.dumps(llm_response))

    cands = await contextual_extract_fields(
        blocks,
        {"recipient_name": {"type": "string", "semantic_role": "recipient"}},
        ["recipient_name"],
        context,
        client=client,
    )
    assert len(cands) == 1
    assert cands[0].value == "Alex Demo"
    assert cands[0].block_id == "b5"
    assert cands[0].source == "llm_context"
    assert cands[0].bbox == blocks[0].bbox


@pytest.mark.asyncio
async def test_contextual_extract_resolves_block_from_evidence_when_id_wrong() -> None:
    """When the LLM cites a bad block_id, match evidence_text to the correct layout block."""

    blocks = [
        TextBlock(
            id="b0",
            page=1,
            bbox=(10.0, 10.0, 200.0, 80.0),
            text="Alex Demo NIF: 45171814K",
        ),
        TextBlock(
            id="b2",
            page=1,
            bbox=(10.0, 220.0, 140.0, 230.0),
            text="Invoice Nº: A-0000713",
        ),
        TextBlock(
            id="b6",
            page=1,
            bbox=(500.0, 280.0, 560.0, 295.0),
            text="4.500,00 €",
        ),
    ]
    context = DocumentContext(document_type="invoice", summary="Invoice", regions=())
    llm_response = {
        "fields": {
            "invoice_number": {
                "value": "A-0000713",
                "block_id": "b0",
                "evidence_text": "Invoice Nº: A-0000713",
            },
            "total_due": {
                "value": 4500.0,
                "block_id": "b0",
                "evidence_text": "4.500,00 €",
            },
        }
    }
    client = AsyncMock(spec=OllamaLLMClient)
    client.complete = AsyncMock(return_value=json.dumps(llm_response))
    fields_spec = {
        "invoice_number": {"type": "string"},
        "total_due": {"type": "number"},
    }

    cands = await contextual_extract_fields(
        blocks,
        fields_spec,
        ["invoice_number", "total_due"],
        context,
        client=client,
    )
    by_field = {c.field: c for c in cands}
    assert by_field["invoice_number"].block_id == "b2"
    assert by_field["invoice_number"].bbox == blocks[1].bbox
    assert by_field["total_due"].block_id == "b6"
    assert by_field["total_due"].bbox == blocks[2].bbox
