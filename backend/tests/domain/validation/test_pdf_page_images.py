"""PDF page rasterization and sparse-text heuristics for vision fallback."""

from __future__ import annotations

import fitz

from ocean_read.domain.validation.pdf_blocks import parse_pdf_blocks
from ocean_read.domain.validation.pdf_page_images import (
    pdf_text_is_sparse,
    render_pdf_page_images,
)


def _image_only_pdf_bytes() -> bytes:
    """Single-page PDF with a raster image and almost no extractable text."""

    doc = fitz.open()
    page = doc.new_page(width=400, height=300)
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 80, 40), False)
    pix.clear_with(200)
    page.insert_image(fitz.Rect(50, 50, 250, 200), pixmap=pix)
    data = doc.tobytes()
    doc.close()
    return data


def test_render_pdf_page_images_returns_png() -> None:
    data = _image_only_pdf_bytes()
    pages = render_pdf_page_images(data, max_pages=2)
    assert len(pages) == 1
    assert pages[0].page == 1
    assert pages[0].png_bytes[:8] == b"\x89PNG\r\n\x1a\n"
    assert pages[0].base64


def test_pdf_text_is_sparse_for_image_only_pdf() -> None:
    data = _image_only_pdf_bytes()
    blocks = parse_pdf_blocks(data)
    assert pdf_text_is_sparse(blocks, data) is True
