"""Schema-driven layout extraction for non-wine documents (e.g. invoices)."""

from __future__ import annotations

import fitz

from ocean_read.domain.validation.extractors_schema import ensemble_schema_extractors
from ocean_read.domain.validation.pdf_blocks import parse_pdf_blocks


def _invoice_like_pdf() -> bytes:
    doc = fitz.open()
    p = doc.new_page()
    p.insert_text((50, 50), "Número de facturaDOEA864B-0011")
    p.insert_text((50, 70), "Fecha de emisión9 de agosto de 2025")
    p.insert_text((50, 90), "ap.demo@acme-supply.test")
    p.insert_text((50, 110), "Importe por pagarUSD20.00")
    data = doc.tobytes()
    doc.close()
    return data


def test_ensemble_schema_extracts_invoice_fields_without_regex_hint() -> None:
    blocks = parse_pdf_blocks(_invoice_like_pdf())
    schema = {
        "invoice_number": {"type": "string", "required": True},
        "invoice_issue_date": {"type": "date", "required": True},
        "recipient_email": {"type": "string", "required": True},
        "total_due": {"type": "number", "required": True},
    }
    cands = ensemble_schema_extractors(blocks, schema)
    by_field = {c.field: c for c in cands}
    assert "DOEA864B-0011" in str(by_field.get("invoice_number", object()).value)
    assert "acme-supply" in str(by_field.get("recipient_email", object()).value)
    assert by_field.get("total_due") and float(by_field["total_due"].value) == 20.0
