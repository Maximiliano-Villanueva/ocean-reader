"""
Docling PDF parsing for the validation pipeline.

Produces **markdown** (LLM extraction input) and **TextBlock** geometry (PDF highlight boxes)
from Docling's JSON export. Optional embedded-image analysis when ``read_images`` is enabled.
"""

from __future__ import annotations

import base64
import io
import logging
from dataclasses import dataclass, field
from typing import Any

from ocean_read.domain.validation.pdf_blocks import TextBlock

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DoclingPictureRef:
    """One embedded picture with geometry for evidence linking."""

    id: str
    page: int
    bbox: tuple[float, float, float, float]
    caption: str | None = None
    image_base64_png: str | None = None


@dataclass
class DoclingParseResult:
    """Dual representation of a parsed PDF."""

    markdown: str
    docling_json: dict[str, Any]
    blocks: list[TextBlock] = field(default_factory=list)
    pictures: list[DoclingPictureRef] = field(default_factory=list)
    image_markdown: str = ""


def _encode_pil_png(pil: Any) -> str | None:
    try:
        buf = io.BytesIO()
        pil.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode("ascii")
    except Exception:
        return None


def _extract_picture_refs(document: Any, docling_json: dict[str, Any]) -> list[DoclingPictureRef]:
    """Pair Docling picture objects with JSON geometry."""

    refs = pictures_from_docling_dict(docling_json)
    if not hasattr(document, "pictures"):
        return refs
    pic_objs = list(document.pictures)
    out: list[DoclingPictureRef] = []
    for i, ref in enumerate(refs):
        image_b64: str | None = None
        if i < len(pic_objs):
            pic_obj = pic_objs[i]
            try:
                image = pic_obj.get_image() if hasattr(pic_obj, "get_image") else None
                pil = getattr(image, "pil_image", None) if image is not None else None
                if pil is not None:
                    image_b64 = _encode_pil_png(pil)
            except Exception as exc:
                logger.info("Docling picture %s skipped: %s", ref.id, exc)
        out.append(
            DoclingPictureRef(
                id=ref.id,
                page=ref.page,
                bbox=ref.bbox,
                caption=ref.caption,
                image_base64_png=image_b64,
            )
        )
    return out


def docling_bbox_to_top_left(
    bbox: dict[str, Any],
    *,
    page_height: float,
) -> tuple[float, float, float, float]:
    """Convert Docling ``BOTTOMLEFT`` bbox to PyMuPDF-style top-left coordinates."""

    left = float(bbox.get("l", 0.0))
    right = float(bbox.get("r", 0.0))
    top = float(bbox.get("t", 0.0))
    bottom = float(bbox.get("b", 0.0))
    y0 = page_height - top
    y1 = page_height - bottom
    return (left, y0, right, y1)


def _page_heights(doc: dict[str, Any]) -> dict[int, float]:
    pages = doc.get("pages") or {}
    out: dict[int, float] = {}
    if isinstance(pages, dict):
        for key, spec in pages.items():
            if not isinstance(spec, dict):
                continue
            page_no = int(spec.get("page_no") or key)
            size = spec.get("size") or {}
            height = float(size.get("height") or 842.0)
            out[page_no] = height
    return out


def blocks_from_docling_dict(doc: dict[str, Any]) -> list[TextBlock]:
    """Build ``TextBlock`` list from Docling ``export_to_dict()`` (evidence / regex extractors)."""

    heights = _page_heights(doc)
    blocks: list[TextBlock] = []
    idx = 0

    def _append(text: str, page_no: int, bbox_raw: dict[str, Any], label: str | None) -> None:
        nonlocal idx
        text = (text or "").strip()
        if not text:
            return
        page_h = heights.get(page_no, 842.0)
        bbox = docling_bbox_to_top_left(bbox_raw, page_height=page_h)
        blocks.append(
            TextBlock(
                id=f"b{idx}",
                page=page_no,
                bbox=bbox,
                text=text,
                section_label=label,
                font_size_max=None,
            )
        )
        idx += 1

    texts = doc.get("texts") or []
    if isinstance(texts, list):
        for item in texts:
            if not isinstance(item, dict):
                continue
            text = str(item.get("text") or item.get("orig") or "")
            label = str(item.get("label") or "") or None
            prov_list = item.get("prov") or []
            if not isinstance(prov_list, list) or not prov_list:
                continue
            prov = prov_list[0] if isinstance(prov_list[0], dict) else {}
            page_no = int(prov.get("page_no") or 1)
            bbox_raw = prov.get("bbox") or {}
            if isinstance(bbox_raw, dict):
                _append(text, page_no, bbox_raw, label)

    tables = doc.get("tables") or []
    if isinstance(tables, list):
        for table in tables:
            if not isinstance(table, dict):
                continue
            prov_list = table.get("prov") or []
            if not isinstance(prov_list, list) or not prov_list:
                continue
            prov = prov_list[0] if isinstance(prov_list[0], dict) else {}
            page_no = int(prov.get("page_no") or 1)
            bbox_raw = prov.get("bbox") or {}
            cells = table.get("data") or table.get("grid") or []
            cell_text = _table_cells_to_text(cells)
            if cell_text and isinstance(bbox_raw, dict):
                _append(cell_text, page_no, bbox_raw, "table")

    return blocks


def _table_cells_to_text(cells: Any) -> str:
    if not isinstance(cells, list):
        return ""
    rows: list[str] = []
    for row in cells:
        if isinstance(row, list):
            parts = [str(c).strip() for c in row if str(c).strip()]
            if parts:
                rows.append(" | ".join(parts))
        elif isinstance(row, dict):
            val = str(row.get("text") or row.get("value") or "").strip()
            if val:
                rows.append(val)
    return "\n".join(rows)


def pictures_from_docling_dict(doc: dict[str, Any]) -> list[DoclingPictureRef]:
    """Picture refs with bboxes (no raster) from Docling JSON."""

    heights = _page_heights(doc)
    out: list[DoclingPictureRef] = []
    pictures = doc.get("pictures") or []
    if not isinstance(pictures, list):
        return out
    for i, pic in enumerate(pictures):
        if not isinstance(pic, dict):
            continue
        prov_list = pic.get("prov") or []
        if not isinstance(prov_list, list) or not prov_list:
            continue
        prov = prov_list[0] if isinstance(prov_list[0], dict) else {}
        page_no = int(prov.get("page_no") or 1)
        bbox_raw = prov.get("bbox") or {}
        if not isinstance(bbox_raw, dict):
            continue
        page_h = heights.get(page_no, 842.0)
        bbox = docling_bbox_to_top_left(bbox_raw, page_height=page_h)
        captions = pic.get("captions") or []
        caption = None
        if isinstance(captions, list) and captions:
            caption = str(captions[0]) if captions[0] else None
        out.append(DoclingPictureRef(id=f"img{i}", page=page_no, bbox=bbox, caption=caption))
    return out


def _build_converter(*, read_images: bool) -> Any:
    try:
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.document_converter import DocumentConverter, PdfFormatOption
    except ImportError as exc:
        raise RuntimeError(
            "docling is not installed. Install with: uv pip install -e \".[docling]\""
        ) from exc

    opts = PdfPipelineOptions()
    opts.do_ocr = False
    opts.do_table_structure = False
    opts.generate_picture_images = read_images
    opts.do_picture_description = False
    return DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opts)},
    )


def parse_pdf_with_docling(pdf_bytes: bytes, *, read_images: bool = False) -> DoclingParseResult:
    """
    Parse PDF via Docling.

    Returns markdown for LLM prompts and blocks derived from JSON for highlight boxes.
    """

    import tempfile
    from pathlib import Path

    converter = _build_converter(read_images=read_images)
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(pdf_bytes)
        tmp_path = Path(tmp.name)
    try:
        document = converter.convert(str(tmp_path)).document
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass

    docling_json = document.export_to_dict()
    markdown = document.export_to_markdown() or ""
    blocks = blocks_from_docling_dict(docling_json)
    pictures = _extract_picture_refs(document, docling_json) if read_images else []

    return DoclingParseResult(
        markdown=markdown,
        docling_json=docling_json,
        blocks=blocks,
        pictures=pictures,
    )
