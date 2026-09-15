"""Spanish prose date extraction from PDF blocks."""

from __future__ import annotations

from ocean_read.domain.validation.extractors_schema import extract_regex_from_schema
from ocean_read.domain.validation.pdf_blocks import TextBlock


def test_spanish_issue_date_extracted_from_labeled_line() -> None:
    blocks = [
        TextBlock(
            id="b1",
            page=1,
            text="Fecha de emisión: 9 de agosto de 2025",
            bbox=(10.0, 10.0, 200.0, 30.0),
        ),
    ]
    fields = {
        "issue_date": {
            "type": "date",
            "aliases": ["Fecha de emisión"],
            "regex_hint": r"\d{1,2}[-/]\d{1,2}[-/]\d{2,4}",
        },
    }
    cands = extract_regex_from_schema(blocks, fields)
    values = [c.value for c in cands if c.field == "issue_date"]
    assert any("agosto" in str(v).lower() for v in values)
