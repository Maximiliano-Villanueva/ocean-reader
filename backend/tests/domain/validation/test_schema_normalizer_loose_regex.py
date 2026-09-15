"""Normalizer repairs agent-authored regex hints that match too broadly."""

from __future__ import annotations

from ocean_read.domain.validation.schema_normalizer import normalize_schema_body


def test_loose_invoice_number_regex_replaced() -> None:
    body = {
        "version": "3",
        "fields": {
            "invoice_number": {
                "type": "string",
                "required": True,
                "aliases": ["Número de factura"],
                "regex_hint": "[A-Z0-9\\-]+",
            },
        },
    }
    out = normalize_schema_body(body)
    hint = out["fields"]["invoice_number"]["regex_hint"]
    assert "número" in hint.lower() or "numero" in hint.lower() or "invoice" in hint.lower()
    assert out["fields"]["invoice_number"].get("on_ambiguity") == "first"
