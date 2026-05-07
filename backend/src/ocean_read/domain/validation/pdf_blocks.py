"""PyMuPDF-based PDF parsing into stable text blocks with geometry for evidence."""

from __future__ import annotations

import statistics
from dataclasses import dataclass


@dataclass(frozen=True)
class TextBlock:
    """One layout text block from ``page.get_text('dict')`` — traceability unit."""

    id: str
    page: int
    bbox: tuple[float, float, float, float]
    text: str
    section_label: str | None = None
    font_size_max: float | None = None


def infer_section_labels(blocks: list[TextBlock]) -> list[TextBlock]:
    """Infer heading sections using font-size heuristics (short + larger than median or ALL CAPS)."""

    if not blocks:
        return []
    sizes = [b.font_size_max or 10.0 for b in blocks]
    med = statistics.median(sizes) if sizes else 10.0
    current: str | None = None
    out: list[TextBlock] = []
    for b in blocks:
        t = b.text.strip()
        line0 = t.split("\n", 1)[0].strip()
        fmax = b.font_size_max or 10.0
        short = len(line0) < 80
        big = fmax > med + 1.5
        all_caps = len(line0) > 2 and line0.isupper() and line0.replace(" ", "").isalpha()
        looks_heading = (big and short) or (all_caps and short)
        if looks_heading and ":" not in line0:
            current = t.split("\n", 1)[0].strip()
            section_label: str | None = None
        else:
            section_label = current
        out.append(
            TextBlock(
                id=b.id,
                page=b.page,
                bbox=b.bbox,
                text=b.text,
                section_label=section_label,
                font_size_max=b.font_size_max,
            )
        )
    return out


def parse_pdf_blocks(data: bytes) -> list[TextBlock]:
    """Extract text blocks with bounding boxes; assigns stable ``b{n}`` ids in document order."""

    import fitz  # PyMuPDF — lazy import keeps tests import-light when mocked

    doc = fitz.open(stream=data, filetype="pdf")
    raw: list[TextBlock] = []
    global_idx = 0
    try:
        for page_idx in range(len(doc)):
            page = doc[page_idx]
            page_num = page_idx + 1
            d = page.get_text("dict")
            for block in d.get("blocks") or []:
                if block.get("type") != 0:
                    continue
                bbox_raw = block.get("bbox") or (0.0, 0.0, 0.0, 0.0)
                bbox = tuple(float(x) for x in bbox_raw)
                parts: list[str] = []
                sizes: list[float] = []
                for line in block.get("lines") or []:
                    for span in line.get("spans") or []:
                        parts.append(str(span.get("text") or ""))
                        sz = span.get("size")
                        if isinstance(sz, (int, float)):
                            sizes.append(float(sz))
                text = "".join(parts).strip()
                if not text:
                    continue
                bid = f"b{global_idx}"
                global_idx += 1
                fmax = max(sizes) if sizes else None
                raw.append(
                    TextBlock(
                        id=bid,
                        page=page_num,
                        bbox=bbox,
                        text=text,
                        section_label=None,
                        font_size_max=fmax,
                    )
                )
    finally:
        doc.close()
    return infer_section_labels(raw)
