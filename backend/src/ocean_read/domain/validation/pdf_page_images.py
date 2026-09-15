"""
Render PDF pages to PNG for multimodal LLM extraction when layout text is sparse or absent.
"""

from __future__ import annotations

import base64
import io
from dataclasses import dataclass

from ocean_read.domain.validation.pdf_blocks import TextBlock


@dataclass(frozen=True)
class PageImage:
    """One rendered page as PNG bytes and base64 for vision APIs."""

    page: int
    png_bytes: bytes
    width: int
    height: int

    @property
    def base64(self) -> str:
        return base64.b64encode(self.png_bytes).decode("ascii")

    @property
    def data_url(self) -> str:
        return f"data:image/png;base64,{self.base64}"


def render_pdf_page_images(
    pdf_bytes: bytes,
    *,
    max_pages: int = 4,
    scale: float = 2.0,
) -> list[PageImage]:
    """Rasterize up to ``max_pages`` pages to PNG (PyMuPDF pixmap)."""

    import fitz

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    out: list[PageImage] = []
    try:
        n = min(len(doc), max(1, max_pages))
        for i in range(n):
            page = doc[i]
            mat = fitz.Matrix(scale, scale)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            png = pix.tobytes("png")
            out.append(PageImage(page=i + 1, png_bytes=png, width=pix.width, height=pix.height))
    finally:
        doc.close()
    return out


def pdf_text_is_sparse(blocks: list[TextBlock], pdf_bytes: bytes) -> bool:
    """Heuristic: scanned/image PDFs yield few or empty layout text blocks."""

    import fitz

    total_chars = sum(len((b.text or "").strip()) for b in blocks)
    if total_chars < 60:
        return True
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        for page in doc:
            text_len = len((page.get_text() or "").strip())
            has_images = bool(page.get_images())
            if has_images and text_len < 50:
                return True
    finally:
        doc.close()
    return False


def page_bbox(page_number: int, pdf_bytes: bytes) -> tuple[float, float, float, float]:
    """Full-page bbox in PDF points for evidence anchoring on vision-sourced values."""

    import fitz

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        page = doc[page_number - 1]
        r = page.rect
        return (float(r.x0), float(r.y0), float(r.x1), float(r.y1))
    finally:
        doc.close()
