"""Tests for span-level PDF blocks and M3 group block selection."""

from __future__ import annotations

from ocean_read.domain.validation.pdf_blocks import TextBlock

from ocean_read.domain.validation.repeating_groups import extract_table_rows_bbox_only


def test_extract_table_rows_bbox_only_one_row_four_columns() -> None:
    """Manual span blocks: same baseline, horizontal gap → multiple cells for table extraction."""

    # Simulates four table cells on one row (y ≈ 100).
    blocks = [
        TextBlock("s0", 1, (50.0, 100.0, 65.0, 112.0), "Alpha", "Results", 10.0),
        TextBlock("s1", 1, (130.0, 100.0, 155.0, 112.0), "10", "Results", 10.0),
        TextBlock("s2", 1, (200.0, 100.0, 215.0, 112.0), "0", "Results", 10.0),
        TextBlock("s3", 1, (260.0, 100.0, 295.0, 112.0), "100", "Results", 10.0),
    ]
    spec = {
        "section_hint": "Results",
        "structure_hint": "table",
        "row_fields": {
            "parameter": {"type": "string"},
            "measured_value": {"type": "number"},
            "lower_bound": {"type": "number"},
            "upper_bound": {"type": "number"},
        },
    }
    rows = extract_table_rows_bbox_only(blocks, "g", spec, column_gap_pt=12.0, row_y_tolerance_pt=4.0)
    assert len(rows) == 1
    assert rows[0]["parameter"] == "Alpha"
    assert rows[0]["measured_value"] == 10.0
    assert rows[0]["lower_bound"] == 0.0
    assert rows[0]["upper_bound"] == 100.0
