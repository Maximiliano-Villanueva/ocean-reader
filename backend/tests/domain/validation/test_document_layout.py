"""Layout serialization for contextual PDF understanding."""

from __future__ import annotations

from ocean_read.domain.validation.document_layout import infer_column_band, serialize_blocks_for_llm
from ocean_read.domain.validation.pdf_blocks import TextBlock


def test_infer_column_band_left_and_right() -> None:
    left = TextBlock(id="b0", page=1, bbox=(10.0, 10.0, 90.0, 40.0), text="Issuer")
    right = TextBlock(id="b1", page=1, bbox=(320.0, 10.0, 500.0, 40.0), text="Recipient")
    pw = 520.0
    assert infer_column_band(left, page_width=pw) == "left"
    assert infer_column_band(right, page_width=pw) == "right"


def test_serialize_includes_block_ids_and_columns() -> None:
    blocks = [
        TextBlock(id="b0", page=1, bbox=(10.0, 10.0, 100.0, 30.0), text="Facturar a Max"),
        TextBlock(id="b1", page=1, bbox=(300.0, 10.0, 500.0, 30.0), text="Cursor issuer"),
    ]
    text = serialize_blocks_for_llm(blocks)
    assert "b0" in text and "col=left" in text
    assert "b1" in text and "col=right" in text
