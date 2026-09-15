"""Repair incomplete top-level ``open_ended`` entries from agent output."""

from __future__ import annotations

from ocean_read.domain.validation.schema_dsl import collect_schema_dsl_errors
from ocean_read.domain.validation.schema_normalizer import normalize_schema_body


def test_normalize_top_level_open_ended_missing_extract_prompt() -> None:
    """Agent often puts ``description`` / ``prompt`` instead of ``extract_prompt``."""

    raw = {
        "version": "3",
        "fields": {
            "recipient_email": {
                "type": "string",
                "required": True,
                "rules": [{"rule_name": "equals", "value": "ap.demo@acme-supply.test"}],
            },
            "total_due": {
                "type": "number",
                "required": True,
                "rules": [{"rule_name": "equals", "value": 20}],
            },
        },
        "rules": ["required", "range_validation", "type_check"],
        "open_ended": {
            "recipient_name": {"description": "Name of the invoice recipient", "informative_only": True},
            "recipient_address": {"prompt": "Full postal address of the bill-to recipient"},
            "invoice_number": {"extraction_prompt": "Extract the invoice number using document context"},
        },
    }
    out = normalize_schema_body(raw)
    oe = out["open_ended"]
    assert oe["recipient_name"]["extract_prompt"] == "Name of the invoice recipient"
    assert oe["recipient_address"]["extract_prompt"] == "Full postal address of the bill-to recipient"
    assert oe["invoice_number"]["extract_prompt"] == "Extract the invoice number using document context"
    assert oe["recipient_address"]["informative_only"] is True
    assert oe["invoice_number"]["informative_only"] is True
    assert "description" not in oe["recipient_name"]
    assert collect_schema_dsl_errors(out) == []


def test_normalize_open_ended_defaults_extract_prompt_from_field_name() -> None:
    raw = {
        "version": "3",
        "fields": {},
        "rules": [],
        "open_ended": {"recipient_name": {}},
    }
    out = normalize_schema_body(raw)
    assert "recipient name" in out["open_ended"]["recipient_name"]["extract_prompt"].lower()
    assert out["open_ended"]["recipient_name"]["informative_only"] is True
    assert collect_schema_dsl_errors(out) == []
