"""Docling PDF parse: markdown for LLM, JSON-derived blocks for evidence bboxes."""

from __future__ import annotations

from ocean_read.domain.validation.docling_parse import (
    blocks_from_docling_dict,
    docling_bbox_to_top_left,
)


def test_docling_bbox_converts_bottom_left_to_top_left() -> None:
    # Page 842pt tall; box near top of page in PDF coordinates.
    bbox = {"l": 50.0, "t": 809.8, "r": 124.58, "b": 789.45, "coord_origin": "BOTTOMLEFT"}
    x0, y0, x1, y1 = docling_bbox_to_top_left(bbox, page_height=842.0)
    assert x0 == 50.0
    assert x1 == 124.58
    assert 30 < y0 < 40
    assert 50 < y1 < 60


def test_blocks_from_docling_dict_assigns_stable_ids() -> None:
    doc = {
        "pages": {"1": {"size": {"width": 595.0, "height": 842.0}, "page_no": 1}},
        "texts": [
            {
                "text": "Factura",
                "label": "section_header",
                "prov": [
                    {
                        "page_no": 1,
                        "bbox": {
                            "l": 50.0,
                            "t": 809.8,
                            "r": 124.58,
                            "b": 789.45,
                            "coord_origin": "BOTTOMLEFT",
                        },
                    }
                ],
            },
            {
                "text": "DOEA864B-0011",
                "label": "text",
                "prov": [
                    {
                        "page_no": 1,
                        "bbox": {
                            "l": 200.0,
                            "t": 750.0,
                            "r": 280.0,
                            "b": 735.0,
                            "coord_origin": "BOTTOMLEFT",
                        },
                    }
                ],
            },
        ],
    }
    blocks = blocks_from_docling_dict(doc)
    assert len(blocks) == 2
    assert blocks[0].id == "b0"
    assert blocks[0].text == "Factura"
    assert blocks[0].page == 1
    assert len(blocks[0].bbox) == 4
