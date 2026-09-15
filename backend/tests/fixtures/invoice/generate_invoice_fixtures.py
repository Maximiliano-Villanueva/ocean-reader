#!/usr/bin/env python3
"""Generate invoice-style PDF corpus for open-ended + strict + cross-field tests.

Includes ``inv_cursor_formatted.pdf``: Spanish layout with sender/recipient columns
and a bordered line-item table (Cursor-style reference).

Run::

    uv run python backend/tests/fixtures/invoice/generate_invoice_fixtures.py
"""

from __future__ import annotations

import json
from pathlib import Path

from invoice_pdf_builder import (
    InvoiceDocumentSpec,
    InvoiceLineItem,
    InvoiceParty,
    build_invoice_pdf,
)


def _here() -> Path:
    return Path(__file__).resolve().parent


def _cursor_style_spec(*, invoice_no: str, total: float, due_date: str) -> InvoiceDocumentSpec:
    """Layout modeled on a real SaaS invoice (Factura + two party columns + table)."""

    unit = total
    return InvoiceDocumentSpec(
        invoice_number=invoice_no,
        issue_date="9 de agosto de 2025",
        due_date=due_date,
        sender=InvoiceParty(
            title="Cursor",
            lines=(
                "801 West End Avenue",
                "New York, New York 10025",
                "Estados Unidos",
                "+1 831-425-9504",
                "hi@cursor.com",
            ),
        ),
        recipient=InvoiceParty(
            title="Facturar a",
            lines=(
                "Alex Demo",
                "123 Demo Street",
                "08001 Barcelona",
                "España",
                "ap.demo@acme-supply.test",
            ),
        ),
        line_items=(
            InvoiceLineItem(
                description="Cursor Pro",
                detail="9 ago 2025 – 9 sept 2025",
                quantity=1,
                unit_price=unit,
            ),
        ),
        summary_sentence=f"USD{total:.2f} con fecha de vencimiento del {due_date}",
        pay_online_label="Pagar en línea",
    )


def main() -> None:
    base = _here()

    schema = {
        "version": "3",
        "fields": {
            "invoice_number": {
                "type": "string",
                "required": True,
                "aliases": ["Número de factura", "Numero de factura"],
                "regex_hint": "(?i)(?:invoice\\s*number|n[uú]mero\\s*de\\s*factura)\\s*[:\\s]+([A-Z0-9-]+)",
            },
            "total_usd": {
                "type": "number",
                "required": True,
                "min": 0,
                "max": 100000,
                "aliases": ["Importe por pagar", "Total due", "Total"],
                "regex_hint": "(?i)(?:total\\s*due|importe\\s*por\\s*pagar|total)\\s*[:\\s]*USD?([\\d.]+)",
            },
        },
        "rules": ["required", "range_validation", "type_check"],
        "cross_field_rules": [
            {
                "id": "total_matches_line",
                "expression": "total_usd == 20",
                "error_message": "Total must match line item (USD20.00)",
                "fields": ["total_usd"],
            }
        ],
        "open_ended": {
            "executive_summary": {
                "extract_prompt": "Two-sentence summary of what this invoice is for",
                "informative_only": True,
                "link_evidence": False,
            },
            "payment_terms_ok": {
                "extract_prompt": "Extract the payment due date or terms sentence",
                "evaluate_prompt": (
                    "Given total_usd and invoice_number, does the payment terms sentence "
                    "state due on 9 August 2025? Reply pass, fail, or ambiguous."
                ),
                "informative_only": False,
                "link_evidence": True,
                "depends_on_fields": ["total_usd", "invoice_number"],
                "evaluation_tags": ["pass", "fail", "ambiguous"],
            },
        },
    }
    (base / "schema_invoice_v3.json").write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")

    cases: list[tuple] = [
        (
            "inv_cursor_formatted",
            _cursor_style_spec(
                invoice_no="DOEA864B-0011",
                total=20.0,
                due_date="9 de agosto de 2025",
            ),
            "PASS",
            [],
        ),
        (
            "inv_clean_001",
            _cursor_style_spec(
                invoice_no="DOEA864B-0010",
                total=20.0,
                due_date="9 de agosto de 2025",
            ),
            "PASS",
            [],
        ),
        (
            "inv_fail_total",
            _cursor_style_spec(
                invoice_no="DOEA864B-0099",
                total=99.0,
                due_date="9 de agosto de 2025",
            ),
            "FAIL",
            [{"field": "total_usd", "rule": "total_matches_line"}],
        ),
    ]

    rows: list[dict] = []
    for stem, inv_spec, status, errs in cases:
        pdf = build_invoice_pdf(inv_spec)
        rel = f"{stem}.pdf"
        (base / rel).write_bytes(pdf)
        truth = {
            "invoice_number": inv_spec.invoice_number,
            "total_usd": sum(li.amount for li in inv_spec.line_items),
        }
        (base / f"{stem}.json").write_text(json.dumps(truth, indent=2) + "\n", encoding="utf-8")
        rows.append(
            {
                "id": stem,
                "clean_pdf": rel,
                "clean_truth": f"{stem}.json",
                "expected_status": status,
                "expected_errors": errs,
            }
        )

    (base / "corpus_index.json").write_text(
        json.dumps({"schema": "schema_invoice_v3.json", "rows": rows}, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(rows)} invoice PDFs under {base}")
    print("  Showcase: inv_cursor_formatted.pdf (parties + bordered table)")


if __name__ == "__main__":
    main()
