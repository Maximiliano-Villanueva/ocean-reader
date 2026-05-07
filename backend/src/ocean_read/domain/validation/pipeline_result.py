"""Combined outcome of a full document validation run (may be PASS, FAIL, or AMBIGUOUS)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from ocean_read.domain.validation.engine import FieldRuleOutcome, FieldValidationError
from ocean_read.domain.validation.mapping import AmbiguousFieldInfo


@dataclass(frozen=True)
class PipelineValidationResult:
    """End-to-end pipeline verdict including ambiguity from Stage 5."""

    status: Literal["PASS", "FAIL", "AMBIGUOUS"]
    schema_key: str | None
    schema_version: str | None
    errors: tuple[FieldValidationError, ...]
    ambiguous_fields: tuple[AmbiguousFieldInfo, ...]
    resolved_values: dict[str, Any] | None = None
    schema_body_snapshot: dict[str, Any] | None = None
    field_rule_outcomes: tuple[FieldRuleOutcome, ...] = ()
