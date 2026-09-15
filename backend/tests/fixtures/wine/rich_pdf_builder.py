"""
Build realistic multi-page PDF fixtures: logos, tables, images, and distractor text.

Canonical wine lab values live in a dedicated **Chemical Analysis** block on page 1 so
deterministic extractors keep the same PASS/FAIL/AMBIGUOUS outcomes as the flat corpus.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class LabValues:
    """Target readings for the wine QA section."""

    ph: float | None = None
    alcohol: float | None = None
    quality: int | None = None
    omit_quality: bool = False


def _logo_png_bytes() -> bytes:
    """Small RGB logo placeholder (wine / lab brand)."""

    from PIL import Image, ImageDraw

    im = Image.new("RGB", (120, 48), color=(45, 55, 72))
    draw = ImageDraw.Draw(im)
    draw.ellipse((8, 8, 40, 40), fill=(180, 60, 80))
    draw.rectangle((50, 14, 110, 34), fill=(230, 230, 235))
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def _chart_png_bytes() -> bytes:
    """Fake chart image for page 2."""

    from PIL import Image, ImageDraw

    im = Image.new("RGB", (200, 120), color=(248, 250, 252))
    draw = ImageDraw.Draw(im)
    for i, h in enumerate((40, 70, 55, 90, 60)):
        draw.rectangle((20 + i * 35, 120 - h, 45 + i * 35, 118), fill=(59, 130, 246))
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def build_rich_wine_pdf(
    *,
    lab: LabValues,
    extra_lab_lines: Sequence[str] = (),
    noise_extra: str = "",
    doc_style: str = "lab_report",
) -> bytes:
    """Return PDF bytes with ≥2 pages, table, images, and embedded lab lines."""

    import fitz

    doc = fitz.open()
    logo = _logo_png_bytes()
    chart = _chart_png_bytes()

    # --- Page 1: corporate shell + lab section ---
    p1 = doc.new_page(width=595, height=842)
    p1.insert_image(fitz.Rect(420, 36, 540, 84), stream=logo)
    title = "Wine QA Report (UCI red wine)" if doc_style == "lab_report" else "Laboratory Certificate — Red Wine Batch"
    p1.insert_text((72, 48), title, fontsize=14)
    p1.insert_text((72, 68), "Anysphere Winery · QA Division · Ref DOEA864B-0011", fontsize=9)
    p1.insert_text((72, 82), "Fecha de emisión: 9 de agosto de 2025  ·  Página 1 de 2", fontsize=8)

    # Invoice-style metadata table (distractor numbers)
    p1.insert_text((72, 108), "Resumen de facturación (referencia interna — no usar para QA)", fontsize=9)
    table_rows = [
        ("Descripción", "Cant.", "Precio", "Importe"),
        ("Análisis rutinario", "1", "USD20.00", "USD20.00"),
        ("Muestra control", "1", "USD0.00", "USD0.00"),
    ]
    y = 124.0
    for row in table_rows:
        p1.insert_text((72, y), "  |  ".join(row), fontsize=8)
        y += 14.0

    p1.insert_text((72, y + 8), "—" * 40, fontsize=8)
    y += 22.0
    p1.insert_text((72, y), "SECTION: Chemical Analysis", fontsize=11)
    y += 18.0
    lab_lines: list[str] = []
    if lab.ph is not None:
        lab_lines.append(f"pH: {lab.ph:g}")
    if lab.alcohol is not None:
        lab_lines.append(f"Alcohol: {lab.alcohol:g}%")
    if not lab.omit_quality and lab.quality is not None:
        lab_lines.append(f"Quality: {lab.quality}")
    lab_lines.extend(extra_lab_lines)
    if lab_lines:
        for line in lab_lines:
            p1.insert_text((72, y), line, fontsize=11)
            y += 22.0

    p1.insert_text(
        (72, y + 12),
        "Nota: los valores de facturación y temperatura de bodega no forman parte del informe químico.",
        fontsize=8,
    )
    if noise_extra:
        ny = y + 36.0
        for line in noise_extra.splitlines():
            p1.insert_text((72, ny), line, fontsize=8)
            ny += 14.0

    # --- Page 2: image + batch table + boilerplate ---
    p2 = doc.new_page(width=595, height=842)
    p2.insert_image(fitz.Rect(72, 48, 272, 168), stream=chart)
    p2.insert_text((72, 180), "Anexo B — Métricas de proceso (referencia)", fontsize=10)
    p2.insert_text((72, 198), "Parámetro          Valor      Unidad", fontsize=8)
    for i, (name, val, unit) in enumerate(
        [
            ("Temp. fermentación", "22.7", "°C"),
            ("Presión tanque", "1.03", "bar"),
            ("Serial equipo", "884422", "—"),
            ("Humedad bodega", "61", "%"),
        ]
    ):
        p2.insert_text((72, 214 + i * 14), f"{name:<22} {val:>8} {unit}", fontsize=8)
    p2.insert_text(
        (72, 300),
        "El párrafo siguiente resume la política de calidad corporativa y no sustituye las mediciones "
        "de la sección Chemical Analysis en la página anterior.",
        fontsize=8,
    )
    p2.insert_text((72, 340), "Pagar en línea: https://example.invalid/pay (enlace de prueba)", fontsize=8)
    p2.insert_text((72, 780), "Anysphere, Inc. · US EIN 87-4436547 · Página 2 de 2", fontsize=7)

    out = doc.tobytes()
    doc.close()
    return out
