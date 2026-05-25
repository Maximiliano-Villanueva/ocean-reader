"""Shared validation outcome types (used by rule engine, pipeline, repeating groups)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class FieldValidationError:
    field: str
    value: Any
    expected: Any
    rule: str
    evidence: dict[str, Any] | None


@dataclass(frozen=True)
class FieldRuleOutcome:
    """One check of a single global rule against one field (pass or fail)."""

    field: str
    rule: str
    passed: bool
    value: Any | None = None
    expected: Any | None = None
    evidence: dict[str, Any] | None = None


@dataclass(frozen=True)
class ValidationReport:
    """Result of schema validation (Stages 7–8); ``status`` is PASS or FAIL only.

    ``AMBIGUOUS`` is assigned by the pipeline when inconsistency is detected **before**
    :func:`ocean_read.domain.validation.engine.validate_schema` runs.

    ``outcomes`` lists every rule–field check executed (for audit / UI), including passes.
    """

    schema_key: str | None
    schema_version: str | None
    status: str  # PASS | FAIL
    errors: tuple[FieldValidationError, ...]
    outcomes: tuple[FieldRuleOutcome, ...]
