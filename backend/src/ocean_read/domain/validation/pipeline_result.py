"""Combined outcome of a full document validation run (may be PASS, FAIL, or AMBIGUOUS)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from ocean_read.domain.validation.mapping import AmbiguousFieldInfo
from ocean_read.domain.validation.open_ended_runner import OpenEndedFieldResult
from ocean_read.domain.validation.outcomes import FieldRuleOutcome, FieldValidationError


@dataclass(frozen=True)
class PipelineValidationResult:
    """End-to-end pipeline verdict including ambiguity from Stage 5.

    ``pdf_hash`` fingerprints the upload; ``pipeline_snapshots`` holds JSON-serializable
    intermediate state for M2 persistence (blocks, candidates, field map, inconsistency,
    resolved values).
    """

    status: Literal["PASS", "FAIL", "AMBIGUOUS"]
    schema_key: str | None
    schema_version: str | None
    errors: tuple[FieldValidationError, ...]
    ambiguous_fields: tuple[AmbiguousFieldInfo, ...]
    resolved_values: dict[str, Any] | None = None
    schema_body_snapshot: dict[str, Any] | None = None
    field_rule_outcomes: tuple[FieldRuleOutcome, ...] = ()
    pdf_hash: str = ""
    pipeline_snapshots: dict[str, Any] | None = None
    open_ended_results: tuple[OpenEndedFieldResult, ...] = ()
