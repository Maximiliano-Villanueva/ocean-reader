"""
Serialize PDF text blocks with layout hints for LLM document understanding.

Flat text loses columns (sender vs recipient, totals vs line items). This module preserves
page, bounding box, and coarse horizontal band so models can infer structure without vision.
"""

from __future__ import annotations

from typing import Literal

from ocean_read.domain.validation.pdf_blocks import TextBlock

ColumnBand = Literal["left", "center", "right", "full"]


def _page_width(blocks_on_page: list[TextBlock]) -> float:
    if not blocks_on_page:
        return 600.0
    return max(b.bbox[2] for b in blocks_on_page) or 600.0


def infer_column_band(block: TextBlock, *, page_width: float) -> ColumnBand:
    """Coarse column from x-center vs page width (works when PDF columns survive as x-offset)."""

    x0, _, x1, _ = block.bbox
    mid = (x0 + x1) / 2.0
    third = page_width / 3.0
    if mid < third:
        return "left"
    if mid > 2 * third:
        return "right"
    if (x1 - x0) > page_width * 0.55:
        return "full"
    return "center"


def serialize_blocks_for_llm(
    blocks: list[TextBlock],
    *,
    max_blocks: int = 120,
    max_chars: int = 24_000,
) -> str:
    """Human/LLM-readable block list with ids and layout metadata."""

    if not blocks:
        return "(no text blocks)"
    lines: list[str] = []
    used = 0
    by_page: dict[int, list[TextBlock]] = {}
    for b in blocks:
        by_page.setdefault(b.page, []).append(b)

    count = 0
    for page in sorted(by_page.keys()):
        page_blocks = sorted(by_page[page], key=lambda b: (b.bbox[1], b.bbox[0]))
        pw = _page_width(page_blocks)
        for b in page_blocks:
            if count >= max_blocks:
                break
            col = infer_column_band(b, page_width=pw)
            x0, y0, x1, y1 = (round(v, 1) for v in b.bbox)
            section = b.section_label or ""
            header = (
                f"[{b.id} p{page} col={col} bbox=({x0},{y0})-({x1},{y1})"
                + (f' section="{section}"' if section else "")
                + "]"
            )
            text = (b.text or "").strip().replace("\n", " / ")
            line = f"{header}\n{text}\n"
            if used + len(line) > max_chars:
                break
            lines.append(line)
            used += len(line)
            count += 1
        if count >= max_blocks:
            break
    return "\n".join(lines)


def block_by_id(blocks: list[TextBlock]) -> dict[str, TextBlock]:
    return {b.id: b for b in blocks}


def serialize_block_index_for_evidence(
    blocks: list[TextBlock],
    *,
    max_blocks: int = 200,
    max_chars: int = 16_000,
) -> str:
    """Compact block id → text map for LLM evidence citations alongside markdown."""

    if not blocks:
        return "(no evidence blocks)"
    lines: list[str] = []
    used = 0
    for b in blocks[:max_blocks]:
        text = (b.text or "").strip().replace("\n", " / ")
        line = f"[{b.id} p{b.page}] {text}"
        if used + len(line) > max_chars:
            break
        lines.append(line)
        used += len(line)
    return "\n".join(lines)


def build_llm_document_view(
    *,
    markdown: str | None,
    blocks: list[TextBlock],
    image_markdown: str | None = None,
) -> str:
    """
    Dual Docling view for LLM extraction: readable markdown plus block index for ``block_id`` cites.
    """

    parts: list[str] = []
    md = (markdown or "").strip()
    if md:
        parts.append("# Document (markdown)\n\n" + md)
    if image_markdown and image_markdown.strip():
        parts.append("# Embedded images (vision)\n\n" + image_markdown.strip())
    index = serialize_block_index_for_evidence(blocks)
    if index and index != "(no evidence blocks)":
        parts.append("# Evidence block index\n\n" + index)
    if parts:
        return "\n\n---\n\n".join(parts)
    return serialize_blocks_for_llm(blocks)
