"""M3: LLM cross-field assist payload validation (no network)."""

from __future__ import annotations

import pytest

from ocean_read.domain.validation.schema_expression_assist import validate_llm_cross_field_payload


def test_validate_llm_cross_field_payload_ok() -> None:
    data = {
        "id": "rule_a",
        "expression": "quality >= 5 OR alcohol < 12",
        "error_message": "High alcohol needs quality (alcohol {alcohol})",
    }
    out = validate_llm_cross_field_payload(data, frozenset({"alcohol", "quality", "ph"}))
    assert out["expression"] == "quality >= 5 OR alcohol < 12"
    assert out["id"] == "rule_a"


def test_validate_llm_cross_field_payload_rejects_unknown_identifier() -> None:
    data = {"expression": "x > 0", "error_message": "m"}
    with pytest.raises(ValueError, match="unknown identifiers"):
        validate_llm_cross_field_payload(data, frozenset({"a"}))


def test_validate_llm_cross_field_payload_rejects_non_object() -> None:
    with pytest.raises(ValueError, match="JSON object"):
        validate_llm_cross_field_payload([], frozenset({"a"}))
