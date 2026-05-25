"""Repeating group row extraction (M3)."""

from __future__ import annotations

from ocean_read.domain.validation.pdf_blocks import TextBlock
from ocean_read.domain.validation.repeating_groups import extract_group_rows


def test_extract_group_pipe_delimited_table_rows() -> None:
    spec = {
        "section_hint": "Test Results",
        "structure_hint": "table",
        "row_fields": {
            "parameter": {"type": "string"},
            "measured_value": {"type": "number"},
            "lower_bound": {"type": "number"},
            "upper_bound": {"type": "number"},
        },
    }
    blocks = [
        TextBlock(
            id="b0",
            page=1,
            bbox=(0, 0, 1, 1),
            text="Test Results\nparameter|measured_value|lower_bound|upper_bound\nDilution | 105 | 0 | 100",
            section_label="Test Results",
        )
    ]
    rows = extract_group_rows(blocks, "test_results", spec)
    assert len(rows) == 1
    assert rows[0]["parameter"] == "Dilution"


def test_extract_group_list_rows() -> None:
    spec = {
        "section_hint": "Test Results",
        "row_fields": {
            "parameter": {"type": "string"},
            "measured_value": {"type": "number"},
            "lower_bound": {"type": "number"},
            "upper_bound": {"type": "number"},
        },
    }
    blocks = [
        TextBlock(
            id="b0",
            page=1,
            bbox=(0, 0, 1, 1),
            text="Test Results\nDilution 105 0 100\nWater 50 0 100",
            section_label="Test Results",
        )
    ]
    rows = extract_group_rows(blocks, "test_results", spec)
    assert len(rows) == 2
    assert rows[0]["parameter"] == "Dilution"
    assert rows[0]["measured_value"] == 105.0


def test_extract_group_explicit_table_uses_bbox_spans() -> None:
    """With ``structure_hint: table``, span-level blocks in the section yield rows without pipes."""

    spec = {
        "section_hint": "Test Results",
        "structure_hint": "table",
        "row_fields": {
            "parameter": {"type": "string"},
            "measured_value": {"type": "number"},
            "lower_bound": {"type": "number"},
            "upper_bound": {"type": "number"},
        },
    }
    blocks = [
        TextBlock("s0", 1, (50.0, 200.0, 90.0, 212.0), "Dilution", "Test Results", 10.0),
        TextBlock("s1", 1, (130.0, 200.0, 155.0, 212.0), "105", "Test Results", 10.0),
        TextBlock("s2", 1, (200.0, 200.0, 215.0, 212.0), "0", "Test Results", 10.0),
        TextBlock("s3", 1, (260.0, 200.0, 295.0, 212.0), "100", "Test Results", 10.0),
    ]
    rows = extract_group_rows(blocks, "test_results", spec)
    assert len(rows) == 1
    assert rows[0]["parameter"] == "Dilution"
    assert rows[0]["measured_value"] == 105.0


def test_extract_group_list_multiblock_after_section_header() -> None:
    """PyMuPDF-style one block per line: rows follow a ``Test Results`` header block."""

    spec = {
        "section_hint": "Test Results",
        "structure_hint": "list",
        "row_fields": {
            "parameter": {"type": "string"},
            "measured_value": {"type": "number"},
            "lower_bound": {"type": "number"},
            "upper_bound": {"type": "number"},
        },
    }
    blocks = [
        TextBlock("h", 1, (0, 0, 1, 1), "Test Results", None, 12.0),
        TextBlock("r0", 1, (0, 20, 1, 30), "GoodRow 10 0 100", None, 10.0),
        TextBlock("r1", 1, (0, 40, 1, 50), "BadRow 200 0 100", None, 10.0),
    ]
    rows = extract_group_rows(blocks, "test_results", spec)
    assert len(rows) == 2
    assert rows[1]["measured_value"] == 200.0


def test_extract_group_sections_paragraphs() -> None:
    """``structure_hint: sections`` — blank-line-separated blocks; ``label: value`` lines."""

    spec = {
        "section_hint": "Samples",
        "structure_hint": "sections",
        "row_fields": {
            "moisture": {"type": "number"},
            "ash": {"type": "number"},
        },
    }
    text = (
        "Samples\n\n"
        "Lot A\n"
        "Moisture: 12\n"
        "Ash: 0.1\n\n"
        "Lot B\n"
        "Moisture: 15\n"
        "Ash: 0.2"
    )
    blocks = [TextBlock("b0", 1, (0, 0, 1, 1), text, section_label="Samples")]
    rows = extract_group_rows(blocks, "lots", spec)
    assert len(rows) == 2
    assert rows[0]["moisture"] == 12.0 and rows[0]["ash"] == 0.1
    assert rows[1]["moisture"] == 15.0 and rows[1]["ash"] == 0.2
