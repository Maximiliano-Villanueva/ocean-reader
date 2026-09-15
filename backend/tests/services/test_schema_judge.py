"""Schema judge fallback (no LLM)."""

from __future__ import annotations

import pytest

from ocean_read.services.schema_judge import _fallback_feedback


def test_fallback_feedback_lists_dsl_errors() -> None:
    out = _fallback_feedback(
        schema_body={"version": "3"},
        validation=None,
        dsl_errors=["fields['x']: missing aliases"],
    )
    assert "DSL" in out["summary"]
    assert out["priority"] == "high"
