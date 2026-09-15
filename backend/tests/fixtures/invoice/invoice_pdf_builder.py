"""
Build invoice PDF fixtures: Spanish layout, sender/recipient columns, formatted line-item table.

Uses PyMuPDF vector drawing for table borders (not merged text blocks).
"""

from __future__ import annotations

import io
from dataclasses import dataclass


@dataclass(frozen=True)
class InvoiceParty:
    """Sender or recipient block."""

    title: str
    lines: tuple[str, ...]


@dataclass(frozen=True)
class InvoiceLineItem:
    description: str
    detail: str = ""
    quantity: int = 1
    unit_price: float = 0.0

    @property
    def amount(self) -> float:
        return round(self.quantity * self.unit_price, 2)


@dataclass(frozen=True)
class InvoiceDocumentSpec:
    """Full invoice layout for one PDF."""

    invoice_number: str
    issue_date: str
    due_date: str
    sender: InvoiceParty
    recipient: InvoiceParty
    line_items: tuple[InvoiceLineItem, ...]
    summary_sentence: str = ""
    pay_online_label: str = "Pagar en línea"
    footer_entity: str = "Anysphere, Inc."
    footer_tax_id: str = "US EIN 87-4436547"


def _logo_png_bytes() -> bytes:
    from PIL import Image, ImageDraw

    im = Image.new("RGB", (64, 64), color=(248, 250, 252))
    draw = ImageDraw.Draw(im)
    draw.polygon([(32, 8), (52, 28), (32, 48), (12, 28)], outline=(30, 30, 30), fill=(200, 210, 220))
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def _chart_png_bytes() -> bytes:
    from PIL import Image, ImageDraw

    im = Image.new("RGB", (220, 130), color=(252, 252, 253))
    draw = ImageDraw.Draw(im)
    for i, h in enumerate((35, 65, 50, 85, 55)):
        draw.rectangle((24 + i * 38, 125 - h, 52 + i * 38, 123), fill=(100, 116, 139))
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def build_invoice_pdf(spec: InvoiceDocumentSpec) -> bytes:
    """Return a 2-page PDF with formatted invoice table and party columns."""

    import fitz

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    logo = _logo_png_bytes()

    # Logo top-right
    page.insert_image(fitz.Rect(500, 40, 560, 100), stream=logo)

    y = 48.0
    page.insert_text((50, y), "Factura", fontsize=22)
    y += 36.0

    meta = [
        ("Número de factura", spec.invoice_number),
        ("Fecha de emisión", spec.issue_date),
        ("Fecha de vencimiento", spec.due_date),
    ]
    for label, value in meta:
        page.insert_text((50, y), f"{label}", fontsize=9)
        page.insert_text((200, y), value, fontsize=9)
        y += 16.0

    y += 10.0
    col_top = y
    col_w = 230.0
    left_x = 50.0
    right_x = 320.0

    page.insert_text((left_x, col_top), spec.sender.title, fontsize=11)
    page.insert_text((right_x, col_top), spec.recipient.title, fontsize=11)
    sy = col_top + 18.0
    for i, line in enumerate(spec.sender.lines):
        page.insert_text((left_x, sy + i * 14), line, fontsize=9)
    for i, line in enumerate(spec.recipient.lines):
        page.insert_text((right_x, sy + i * 14), line, fontsize=9)

    y = sy + max(len(spec.sender.lines), len(spec.recipient.lines)) * 14 + 24.0

    total = sum(li.amount for li in spec.line_items)
    if spec.summary_sentence:
        page.insert_text((50, y), spec.summary_sentence, fontsize=11)
        y += 20.0
    page.insert_text((50, y), spec.pay_online_label, fontsize=9)
    y += 28.0

    # --- Formatted table (headers + grid) ---
    table_left = 50.0
    table_right = 545.0
    col_desc = 260.0
    col_qty = 340.0
    col_unit = 410.0
    col_amt = 480.0
    row_h = 22.0
    header_y = y

    headers = [
        (table_left + 4, "Descripción"),
        (col_qty + 4, "Cant."),
        (col_unit + 4, "Precio unitario"),
        (col_amt + 4, "Importe"),
    ]
    for hx, ht in headers:
        page.insert_text((hx, header_y + 5), ht, fontsize=9)

    def hline(ypos: float) -> None:
        page.draw_line(fitz.Point(table_left, ypos), fitz.Point(table_right, ypos), width=0.6, color=(0, 0, 0))

    def vline(xpos: float, y0: float, y1: float) -> None:
        page.draw_line(fitz.Point(xpos, y0), fitz.Point(xpos, y1), width=0.6, color=(0, 0, 0))

    hline(header_y)
    hline(header_y + row_h)
    row_y = header_y + row_h
    for item in spec.line_items:
        page.insert_text((table_left + 4, row_y + 4), item.description, fontsize=9)
        if item.detail:
            page.insert_text((table_left + 4, row_y + 13), item.detail, fontsize=7)
        page.insert_text((col_qty + 8, row_y + 6), str(item.quantity), fontsize=9)
        page.insert_text((col_unit + 4, row_y + 6), f"USD{item.unit_price:.2f}", fontsize=9)
        page.insert_text((col_amt + 4, row_y + 6), f"USD{item.amount:.2f}", fontsize=9)
        row_y += row_h if not item.detail else row_h + 8
        hline(row_y)

    table_bottom = row_y
    vline(table_left, header_y, table_bottom)
    vline(col_qty, header_y, table_bottom)
    vline(col_unit, header_y, table_bottom)
    vline(col_amt, header_y, table_bottom)
    vline(table_right, header_y, table_bottom)

    y = table_bottom + 18.0
    totals = [
        ("Subtotal", total),
        ("Total", total),
        ("Importe por pagar", total),
    ]
    for label, amt in totals:
        page.insert_text((col_unit, y), label, fontsize=9)
        page.insert_text((col_amt, y), f"USD{amt:.2f}", fontsize=9 if label != "Importe por pagar" else 10)
        y += 16.0

    # Machine-readable strict-field lines (separate block, spaced for regex extractors)
    y += 12.0
    page.insert_text((50, y), "SECTION: Invoice data (extraction)", fontsize=8)
    y += 14.0
    page.insert_text((50, y), f"Invoice number: {spec.invoice_number}", fontsize=10)
    y += 14.0
    page.insert_text((50, y), f"Total due: USD{total:.2f}", fontsize=10)
    y += 14.0
    page.insert_text((50, y), f"Fecha de vencimiento: {spec.due_date}", fontsize=9)

    # Page 2 — annex noise (image + distractor table)
    p2 = doc.new_page(width=595, height=842)
    chart = _chart_png_bytes()
    p2.insert_image(fitz.Rect(50, 50, 270, 180), stream=chart)
    p2.insert_text((50, 200), "Anexo — Notas internas (no forman parte de la factura)", fontsize=10)
    p2.insert_text(
        (50, 220),
        "Los valores de temperatura y presión en esta página son ruido de proceso, no importes de factura.",
        fontsize=8,
    )
    p2.insert_text((50, 780), f"{spec.footer_entity} · {spec.footer_tax_id} · Página 2 de 2", fontsize=7)

    out = doc.tobytes()
    doc.close()
    return out
