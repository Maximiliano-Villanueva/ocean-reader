"""
Filter validation runs into cohorts and aggregate PASS/FAIL/AMBIGUOUS statistics.

Used by the Insights tab to let users define saved views (by tags, checklist, revision, outcome).
"""

from __future__ import annotations

from typing import Any, Mapping

from ocean_read.domain.validation.run_attributes import run_attributes_match


def run_matches_cohort(run: Mapping[str, Any], filters: Mapping[str, Any]) -> bool:
    """Return True when a run row matches cohort filter criteria."""

    schema_key = (filters.get("schema_key") or "").strip()
    if schema_key and run.get("schema_key") != schema_key:
        return False

    version_label = (filters.get("version_label") or "").strip()
    if version_label and run.get("version_label") != version_label:
        return False

    outcomes = filters.get("outcomes") or []
    if outcomes and run.get("outcome") not in outcomes:
        return False

    attrs = run.get("attributes") or {}
    required_attrs = filters.get("attributes") or []
    if required_attrs and not run_attributes_match(attrs, required_attrs):
        return False

    return True


def aggregate_outcomes(
    runs: list[Mapping[str, Any]],
    *,
    pass_threshold_pct: float = 100.0,
) -> dict[str, Any]:
    """
    Summarize outcome counts and whether the cohort meets a pass-rate threshold.

    Pass rate = PASS / total × 100 (FAIL and AMBIGUOUS count against the threshold).
    """

    total = len(runs)
    pass_count = sum(1 for r in runs if r.get("outcome") == "PASS")
    fail_count = sum(1 for r in runs if r.get("outcome") == "FAIL")
    ambiguous_count = sum(1 for r in runs if r.get("outcome") == "AMBIGUOUS")
    pass_rate = (pass_count / total * 100.0) if total else 0.0
    threshold = max(0.0, min(100.0, float(pass_threshold_pct)))
    return {
        "total": total,
        "pass_count": pass_count,
        "fail_count": fail_count,
        "ambiguous_count": ambiguous_count,
        "pass_rate_pct": round(pass_rate, 2),
        "pass_threshold_pct": threshold,
        "meets_threshold": pass_rate >= threshold if total else False,
    }
