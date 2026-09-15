"""DSL v3 ``open_ended`` validation."""

from __future__ import annotations

from ocean_read.domain.validation.schema_dsl import collect_schema_dsl_errors


def test_open_ended_requires_version_3() -> None:
    body = {
        "version": "2",
        "fields": {"a": {"type": "number"}},
        "rules": [],
        "open_ended": {"summary": {"extract_prompt": "Summarize", "informative_only": True}},
    }
    errs = collect_schema_dsl_errors(body)
    assert any("version" in e and "3" in e for e in errs)


def test_open_ended_valid_informative() -> None:
    body = {
        "version": "3",
        "fields": {"ph": {"type": "number"}},
        "rules": [],
        "open_ended": {
            "executive_summary": {
                "extract_prompt": "Write a 2-sentence summary",
                "informative_only": True,
                "link_evidence": False,
            }
        },
    }
    assert collect_schema_dsl_errors(body) == []


def test_open_ended_evaluated_requires_evaluate_prompt() -> None:
    body = {
        "version": "3",
        "fields": {"ph": {"type": "number"}},
        "rules": [],
        "open_ended": {
            "quality_check": {"extract_prompt": "Find conclusion paragraph"}
        },
    }
    errs = collect_schema_dsl_errors(body)
    assert any("evaluate_prompt" in e for e in errs)
