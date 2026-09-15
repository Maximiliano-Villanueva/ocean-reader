"""
Golden schema for the invoice agent user prompt (Cursor-formatted PDF E2E).

Represents what the schema agent should produce after normalization — used when Ollama
is not available in CI and as the expected shape for mocked agent tests.

All sample values are synthetic (no real PII).
"""

from __future__ import annotations

from typing import Any

from ocean_read.domain.validation.schema_normalizer import normalize_schema_body

_DEMO_EMAIL = "ap.demo@acme-supply.test"

# Exact user prompt for agent + E2E tests (synthetic demo data).
INV_CURSOR_AGENT_USER_PROMPT = (
    "Extract the name of the recipient of the invoice without validation, "
    "extract the address of the recipient without validation, "
    f"extract the email of the recipient and validate it against {_DEMO_EMAIL}. "
    'Extract the invoice number. Extract "fecha de emisión" and "fecha de vencimiento", '
    "last but not least extract the Total due and validate that is 20.0 USD"
)


def agent_raw_schema_from_prompt() -> dict[str, Any]:
    """Plausible agent draft (pre-normalize) mirroring the user prompt."""

    return {
        "version": "3",
        "fields": {
            "recipient_email": {
                "type": "string",
                "required": True,
                "aliases": ["correo electrónico", "email del destinatario", "email"],
                "semantic_role": "recipient",
                "on_ambiguity": "best_match",
                "rules": [{"rule_name": "equals", "value": _DEMO_EMAIL}],
            },
            "invoice_number": {
                "type": "string",
                "required": True,
                "aliases": ["número de factura", "invoice number"],
                "semantic_role": "document_identifier",
                "on_ambiguity": "first",
                "llm_fallback": True,
                "llm_only": True,
                "extraction_hint": "Extract the unique invoice identifier using document context.",
            },
            "issue_date": {
                "type": "date",
                "required": True,
                "aliases": ["fecha de emisión", "fecha de emision"],
                "semantic_role": "issue_date",
                "llm_fallback": True,
            },
            "due_date": {
                "type": "date",
                "required": True,
                "aliases": ["fecha de vencimiento", "due date"],
                "semantic_role": "due_date",
                "llm_fallback": True,
            },
            "total_due": {
                "type": "number",
                "required": True,
                "aliases": ["Total due", "Importe por pagar", "total a pagar"],
                "semantic_role": "document_total",
                "rules": [{"rule_name": "equals", "value": 20}],
            },
            "recipient_name": {
                "type": "open_ended",
                "extract_prompt": "Extract the full name of the invoice recipient (bill-to party)",
                "informative_only": True,
            },
            "recipient_address": {
                "type": "open_ended",
                "extract_prompt": "Extract the full postal address of the invoice recipient",
                "informative_only": True,
            },
        },
        "rules": ["required", "range_validation", "type_check"],
        "extraction": {"understand_document": True, "context_pass": "when_needed"},
    }


def normalized_inv_cursor_agent_schema() -> dict[str, Any]:
    """DSL-ready schema after ``normalize_schema_body`` (committed JSON matches this)."""

    return normalize_schema_body(agent_raw_schema_from_prompt())


INV_CURSOR_STRICT_TRUTH: dict[str, Any] = {
    "invoice_number": "DOEA864B-0011",
    "recipient_email": _DEMO_EMAIL,
    "issue_date": "9 de agosto de 2025",
    "due_date": "9 de agosto de 2025",
    "total_due": 20.0,
}

INV_CURSOR_OPEN_ENDED_TRUTH: dict[str, str] = {
    "recipient_name": "Alex Demo",
    "recipient_address": "123 Demo Street, Barcelona",
}
