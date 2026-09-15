"""Normalize agent-broken invoice schemas into publishable DSL v3."""

from __future__ import annotations

from ocean_read.domain.validation.schema_dsl import collect_schema_dsl_errors
from ocean_read.domain.validation.schema_normalizer import normalize_schema_body, schema_has_open_ended


def test_normalize_user_invoice_prompt_shape() -> None:
    """Simulates a broken agent schema like the user's invoince @ 1.0."""

    raw = {
        "version": "3",
        "fields": {
            "recipient_name": {
                "type": "open_ended",
                "description": "The name of the recipient",
                "informative_only": True,
            },
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
            "invoice_number": {"type": "string", "required": True},
            "invoice_issue_date": {"type": "date", "required": True},
            "invoice_due_date": {"type": "date", "required": True},
        },
        "rules": ["required", "range_validation", "type_check"],
    }
    out = normalize_schema_body(raw)
    assert "recipient_name" in out.get("open_ended", {})
    assert "recipient_name" not in out.get("fields", {})
    assert out["fields"]["total_due"]["min"] == 20
    assert out["fields"]["total_due"]["max"] == 20
    assert out["fields"]["invoice_number"].get("aliases")
    assert out["fields"]["recipient_email"].get("regex_hint")
    assert collect_schema_dsl_errors(out) == []
    assert schema_has_open_ended(out)


def test_canonicalize_agent_field_key_aliases() -> None:
    raw = {
        "version": "3",
        "fields": {
            "document_total": {"type": "number", "required": True, "min": 20, "max": 20},
            "date_emision": {"type": "date", "required": True, "aliases": ["fecha de emisión"]},
            "date_vencimiento": {"type": "date", "required": True, "aliases": ["fecha de vencimiento"]},
        },
        "rules": ["required"],
    }
    out = normalize_schema_body(raw)
    assert "total_due" in out["fields"]
    assert "issue_date" in out["fields"]
    assert "due_date" in out["fields"]
    assert "document_total" not in out["fields"]


def test_invoice_number_llm_fallback_omits_regex_hint() -> None:
    raw = {
        "version": "3",
        "fields": {
            "invoice_number": {
                "type": "string",
                "required": True,
                "aliases": ["número de factura"],
                "llm_fallback": True,
                "regex_hint": "(?i)[A-Z0-9-]+",
            },
        },
        "rules": ["required"],
    }
    out = normalize_schema_body(raw)
    inv = out["fields"]["invoice_number"]
    assert "regex_hint" not in inv
    assert inv.get("llm_fallback") is True
    assert inv.get("extraction_hint")
    assert collect_schema_dsl_errors(out) == []
