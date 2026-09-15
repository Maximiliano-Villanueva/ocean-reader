#!/usr/bin/env python3
"""
Generate varied supplier invoice PDFs for David Park (AP) persona demos.

Four layouts share extractable fields but differ in visual structure (tables, columns, tax lines).
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

# Allow importing test fixture builder
_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT / "backend" / "tests" / "fixtures" / "invoice"))

from invoice_pdf_builder import (  # noqa: E402
    InvoiceDocumentSpec,
    InvoiceLineItem,
    InvoiceParty,
    build_invoice_pdf,
)


@dataclass(frozen=True)
class InvoiceTruth:
    invoice_number: str
    issue_date: str
    due_date: str
    vendor_name: str
    bill_to_name: str
    subtotal: float
    tax_amount: float
    total_due: float
    line_items_summary: str

    def to_json(self) -> dict:
        return {
            "invoice_number": self.invoice_number,
            "issue_date": self.issue_date,
            "due_date": self.due_date,
            "vendor_name": self.vendor_name,
            "bill_to_name": self.bill_to_name,
            "subtotal_before_tax": self.subtotal,
            "tax_amount": self.tax_amount,
            "total_due": self.total_due,
            "line_items_summary": self.line_items_summary,
        }


def _write(pdf_path: Path, truth_path: Path, pdf_bytes: bytes, truth: InvoiceTruth) -> None:
    pdf_path.write_bytes(pdf_bytes)
    truth_path.write_text(json.dumps(truth.to_json(), indent=2) + "\n", encoding="utf-8")


def build_us_corporate(truth: InvoiceTruth) -> bytes:
    """US letterhead: INVOICE title, Bill To / Remit To, item table, subtotal + sales tax."""

    import fitz

    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    y = 48.0
    page.insert_text((48, y), "ACME INDUSTRIAL SUPPLY LLC", fontsize=14)
    page.insert_text((48, y + 18), "1200 Commerce Drive · Chicago IL 60601", fontsize=8)
    page.insert_text((420, y), "INVOICE", fontsize=20)
    y += 50
    page.insert_text((48, y), f"Invoice #: {truth.invoice_number}", fontsize=10)
    page.insert_text((320, y), f"Issue date: {truth.issue_date}", fontsize=9)
    y += 16
    page.insert_text((320, y), f"Due date: {truth.due_date}", fontsize=9)
    y += 28
    page.insert_text((48, y), "Bill To:", fontsize=10)
    page.insert_text((48, y + 14), truth.bill_to_name, fontsize=9)
    page.insert_text((320, y), "Vendor:", fontsize=10)
    page.insert_text((320, y + 14), truth.vendor_name, fontsize=9)
    y += 50
    # Table header
    page.draw_rect(fitz.Rect(48, y, 564, y + 18), width=0.5)
    page.insert_text((52, y + 5), "Description", fontsize=9)
    page.insert_text((380, y + 5), "Qty", fontsize=9)
    page.insert_text((430, y + 5), "Amount", fontsize=9)
    y += 18
    page.draw_rect(fitz.Rect(48, y, 564, y + 22), width=0.5)
    page.insert_text((52, y + 6), truth.line_items_summary[:80], fontsize=8)
    page.insert_text((382, y + 6), "1", fontsize=9)
    page.insert_text((430, y + 6), f"${truth.subtotal:,.2f}", fontsize=9)
    y += 30
    for label, amt in (
        ("Subtotal", truth.subtotal),
        ("Sales tax", truth.tax_amount),
        ("Total due", truth.total_due),
    ):
        page.insert_text((400, y), label, fontsize=9)
        page.insert_text((480, y), f"${amt:,.2f}", fontsize=10 if label == "Total due" else 9)
        y += 16
    y += 10
    page.insert_text((48, y), f"Invoice number: {truth.invoice_number}", fontsize=9)
    y += 12
    page.insert_text((48, y), f"Subtotal before tax: USD {truth.subtotal:.2f}", fontsize=9)
    y += 12
    page.insert_text((48, y), f"Tax amount: USD {truth.tax_amount:.2f}", fontsize=9)
    y += 12
    page.insert_text((48, y), f"Total due: USD {truth.total_due:.2f}", fontsize=10)
    out = doc.tobytes()
    doc.close()
    return out


def build_uk_vat(truth: InvoiceTruth) -> bytes:
    """UK VAT invoice with right-aligned totals block."""

    import fitz

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((50, 45), "VAT INVOICE", fontsize=18)
    page.insert_text((50, 70), truth.vendor_name, fontsize=11)
    page.insert_text((50, 86), f"Invoice No. {truth.invoice_number}", fontsize=10)
    page.insert_text((50, 102), f"Date: {truth.issue_date}  ·  Due: {truth.due_date}", fontsize=9)
    page.insert_text((50, 130), "Customer:", fontsize=10)
    page.insert_text((50, 146), truth.bill_to_name, fontsize=9)
    page.insert_text((50, 180), "Services / goods:", fontsize=10)
    page.insert_text((50, 196), truth.line_items_summary, fontsize=8)
    y = 240.0
    page.draw_line(fitz.Point(300, y), fitz.Point(545, y))
    y += 12
    for label, amt in (
        ("Net amount", truth.subtotal),
        ("VAT 20%", truth.tax_amount),
        ("Total payable", truth.total_due),
    ):
        page.insert_text((310, y), label, fontsize=9)
        page.insert_text((470, y), f"£{amt:,.2f}", fontsize=10)
        y += 18
    page.insert_text((50, 720), f"Total due: GBP {truth.total_due:.2f}", fontsize=10)
    out = doc.tobytes()
    doc.close()
    return out


def build_minimal(truth: InvoiceTruth) -> bytes:
    """Single-column minimalist startup invoice."""

    import fitz

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    y = 60.0
    page.insert_text((50, y), truth.vendor_name, fontsize=16)
    y += 30
    lines = [
        f"Invoice {truth.invoice_number}",
        f"Issued {truth.issue_date}",
        f"Due {truth.due_date}",
        f"Bill to: {truth.bill_to_name}",
        "",
        truth.line_items_summary,
        "",
        f"Subtotal: ${truth.subtotal:.2f}",
        f"Tax: ${truth.tax_amount:.2f}",
        f"Amount due: ${truth.total_due:.2f}",
    ]
    for line in lines:
        page.insert_text((50, y), line, fontsize=10)
        y += 18
    out = doc.tobytes()
    doc.close()
    return out


def build_ambiguous_total(truth: InvoiceTruth) -> bytes:
    """US layout with duplicate invoice_number values (triggers AMBIGUOUS on extraction)."""

    import fitz

    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    y = 48.0
    page.insert_text((48, y), "ACME INDUSTRIAL SUPPLY LLC", fontsize=14)
    page.insert_text((420, y), "INVOICE", fontsize=20)
    y += 40
    page.insert_text((48, y), f"Invoice #: {truth.invoice_number}", fontsize=10)
    page.insert_text((320, y), f"Issue date: {truth.issue_date}", fontsize=9)
    y += 16
    page.insert_text((320, y), f"Due date: {truth.due_date}", fontsize=9)
    y += 28
    page.insert_text((48, y), "Bill To:", fontsize=10)
    page.insert_text((48, y + 14), truth.bill_to_name, fontsize=9)
    page.insert_text((320, y), "Vendor:", fontsize=10)
    page.insert_text((320, y + 14), truth.vendor_name, fontsize=9)
    y += 50
    page.insert_text((48, y), truth.line_items_summary, fontsize=9)
    y += 30
    page.insert_text((400, y), "Subtotal", fontsize=9)
    page.insert_text((480, y), f"${truth.subtotal:,.2f}", fontsize=9)
    y += 16
    page.insert_text((400, y), "Sales tax", fontsize=9)
    page.insert_text((480, y), f"${truth.tax_amount:,.2f}", fontsize=9)
    y += 16
    page.insert_text((400, y), "Total due", fontsize=10)
    page.insert_text((480, y), f"${truth.total_due:,.2f}", fontsize=10)
    # Conflicting invoice number in footer (different from header → ambiguous invoice_number)
    y = 720.0
    page.insert_text((48, y), f"Invoice number: US-2025-7777", fontsize=10)
    page.insert_text((48, y + 14), f"Total due: USD {truth.total_due:.2f}", fontsize=10)
    page.insert_text((48, y + 28), f"Reference copy — header shows {truth.invoice_number}", fontsize=8)
    out = doc.tobytes()
    doc.close()
    return out


def build_spanish_cursor(truth: InvoiceTruth) -> bytes:
    """Reuse rich Spanish table layout from fixture builder."""

    spec = InvoiceDocumentSpec(
        invoice_number=truth.invoice_number,
        issue_date=truth.issue_date,
        due_date=truth.due_date,
        sender=InvoiceParty(
            title=truth.vendor_name,
            lines=("Barcelona · España", "facturacion@vendor.es"),
        ),
        recipient=InvoiceParty(
            title="Facturar a",
            lines=(truth.bill_to_name, "Nordic Supplies GmbH", "Berlin, Germany"),
        ),
        line_items=(
            InvoiceLineItem(
                description=truth.line_items_summary[:60],
                detail="Entrega Q3",
                quantity=1,
                unit_price=truth.subtotal,
            ),
        ),
        summary_sentence=f"EUR {truth.total_due:.2f} IVA incluido",
    )
    return build_invoice_pdf(spec)


def main() -> None:
    out_dir = Path(__file__).resolve().parent / "david_ap"
    out_dir.mkdir(parents=True, exist_ok=True)

    cases: list[tuple[str, callable, InvoiceTruth]] = [
        (
            "inv_us_acme",
            build_us_corporate,
            InvoiceTruth(
                invoice_number="US-2025-8842",
                issue_date="2025-07-15",
                due_date="2025-08-14",
                vendor_name="Acme Industrial Supply LLC",
                bill_to_name="Nordic Supplies GmbH",
                subtotal=1250.0,
                tax_amount=112.5,
                total_due=1362.5,
                line_items_summary="Hydraulic pumps (4) + installation kit",
            ),
        ),
        (
            "inv_uk_vat",
            build_uk_vat,
            InvoiceTruth(
                invoice_number="GB-VAT-9912",
                issue_date="15 July 2025",
                due_date="14 August 2025",
                vendor_name="Thames Components Ltd",
                bill_to_name="Nordic Supplies GmbH",
                subtotal=800.0,
                tax_amount=160.0,
                total_due=960.0,
                line_items_summary="Consulting hours — warehouse layout review (40h)",
            ),
        ),
        (
            "inv_minimal_saas",
            build_minimal,
            InvoiceTruth(
                invoice_number="SAAS-00441",
                issue_date="2025-07-01",
                due_date="2025-07-31",
                vendor_name="CloudLedger Inc.",
                bill_to_name="Nordic Supplies GmbH AP",
                subtotal=299.0,
                tax_amount=59.8,
                total_due=358.8,
                line_items_summary="Pro plan — 25 seats × 1 month",
            ),
        ),
        (
            "inv_es_formatted",
            build_spanish_cursor,
            InvoiceTruth(
                invoice_number="ES-2025-771",
                issue_date="1 de julio de 2025",
                due_date="31 de julio de 2025",
                vendor_name="Proveedores Mediterráneo S.L.",
                bill_to_name="Nordic Supplies GmbH",
                subtotal=4200.0,
                tax_amount=882.0,
                total_due=5082.0,
                line_items_summary="Materiales de embalaje — palets y film",
            ),
        ),
        (
            "inv_us_fail_tax",
            build_us_corporate,
            InvoiceTruth(
                invoice_number="US-2025-8843-FAIL",
                issue_date="2025-07-16",
                due_date="2025-08-15",
                vendor_name="Acme Industrial Supply LLC",
                bill_to_name="Nordic Supplies GmbH",
                subtotal=500.0,
                tax_amount=50.0,
                total_due=999.0,  # wrong total → FAIL cross-field
                line_items_summary="Emergency spare parts",
            ),
        ),
        (
            "inv_us_ambiguous_total",
            build_ambiguous_total,
            InvoiceTruth(
                invoice_number="US-2025-8844-AMB",
                issue_date="2025-07-17",
                due_date="2025-08-16",
                vendor_name="Acme Industrial Supply LLC",
                bill_to_name="Nordic Supplies GmbH",
                subtotal=750.0,
                tax_amount=67.5,
                total_due=817.5,
                line_items_summary="Mixed fasteners — bulk order",
            ),
        ),
    ]

    index: list[dict] = []
    for stem, builder, truth in cases:
        pdf = builder(truth)
        _write(out_dir / f"{stem}.pdf", out_dir / f"{stem}.json", pdf, truth)
        index.append({"id": stem, "pdf": f"{stem}.pdf", "truth": f"{stem}.json"})
        print(f"Wrote {stem}.pdf")

    (out_dir / "corpus_index.json").write_text(
        json.dumps({"invoices": index}, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
