"""Tests for cohort filtering and outcome aggregation."""

from __future__ import annotations

from ocean_read.domain.validation.cohort_aggregation import aggregate_outcomes, run_matches_cohort


def _run(
    *,
    outcome: str = "PASS",
    schema_key: str = "invoice",
    version_label: str = "1.0",
    attributes: dict[str, str | None] | None = None,
) -> dict:
    return {
        "outcome": outcome,
        "schema_key": schema_key,
        "version_label": version_label,
        "attributes": attributes or {},
    }


def test_run_matches_cohort_by_schema_and_outcome() -> None:
    run = _run(outcome="FAIL", schema_key="wine_quality")
    filters = {"schema_key": "wine_quality", "outcomes": ["FAIL"], "attributes": []}
    assert run_matches_cohort(run, filters)
    assert not run_matches_cohort(run, {**filters, "outcomes": ["PASS"]})


def test_run_matches_cohort_by_attributes() -> None:
    run = _run(attributes={"batch": "Q1", "fixture": None})
    assert run_matches_cohort(run, {"attributes": [{"key": "batch", "value": "Q1"}]})
    assert run_matches_cohort(run, {"attributes": [{"key": "fixture"}]})
    assert not run_matches_cohort(run, {"attributes": [{"key": "batch", "value": "Q2"}]})


def test_aggregate_outcomes_and_threshold() -> None:
    runs = [
        _run(outcome="PASS"),
        _run(outcome="PASS"),
        _run(outcome="FAIL"),
        _run(outcome="AMBIGUOUS"),
    ]
    summary = aggregate_outcomes(runs, pass_threshold_pct=75.0)
    assert summary["total"] == 4
    assert summary["pass_count"] == 2
    assert summary["fail_count"] == 1
    assert summary["ambiguous_count"] == 1
    assert summary["pass_rate_pct"] == 50.0
    assert summary["meets_threshold"] is False

    summary_ok = aggregate_outcomes(runs[:2], pass_threshold_pct=100.0)
    assert summary_ok["meets_threshold"] is True
