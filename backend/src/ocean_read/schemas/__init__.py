"""Pydantic schemas for API payloads."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, ConfigDict


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    settings: dict[str, Any]
    organization_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class LogViewerContainerRead(BaseModel):
    """One Docker container for this Compose project (log viewer)."""

    id: str
    name: str
    service: str
    status: str
    state: str


class LogViewerTailRead(BaseModel):
    container_id: str
    tail: int
    text: str


class ValidationEvidenceOut(BaseModel):
    """Block-level traceability for one extracted field."""

    text: str = ""
    block_id: str = ""
    page: int = 1
    bbox: list[float] | None = None
    section_label: str | None = None


class ValidationFieldErrorOut(BaseModel):
    field: str
    value: Any
    expected: Any
    rule: str
    evidence: ValidationEvidenceOut | None = None


class AmbiguousFieldOut(BaseModel):
    """When pipeline cannot pick a single value for a schema field."""

    field: str
    candidate_count: int


class FieldRuleOutcomeOut(BaseModel):
    """One executed global rule against one schema field (audit row — includes passes)."""

    field: str
    rule: str
    passed: bool
    value: Any | None = None
    expected: Any | None = None
    evidence: ValidationEvidenceOut | None = None


class ValidateDocumentResponse(BaseModel):
    """Result of POST ``/api/validate-document`` — PASS / FAIL / AMBIGUOUS plus structured failures."""

    status: Literal["PASS", "FAIL", "AMBIGUOUS"]
    schema_id: str
    schema_version: str
    results: list[ValidationFieldErrorOut]
    ambiguous_fields: list[AmbiguousFieldOut] = Field(default_factory=list)
    schema_snapshot: dict[str, Any] | None = Field(
        default=None,
        description="Full schema JSON applied for this run (immutable snapshot).",
    )
    resolved_values: dict[str, Any] | None = Field(
        default=None,
        description="Resolved values per field after extraction & resolution (Stage 6).",
    )
    field_rule_outcomes: list[FieldRuleOutcomeOut] = Field(
        default_factory=list,
        description="Each rule×field check, including passes.",
    )
    run_id: str | None = Field(default=None, description="Persisted validation run id (audit history).")


class ValidationRunSummary(BaseModel):
    """One row in the validation history table."""

    id: str
    schema_key: str
    version_label: str
    document_filename: str
    outcome: str
    created_at: str | None = None


class ValidationRunsPage(BaseModel):
    """Paginated validation history for a project (max 25 rows per request)."""

    items: list[ValidationRunSummary]
    total: int
    page: int
    page_size: int


class ValidationRunDetailOut(BaseModel):
    """Full persisted report + optional replay path for the uploaded PDF."""

    id: str
    schema_key: str
    version_label: str
    document_filename: str
    outcome: str
    created_at: str | None = None
    report: ValidateDocumentResponse
    has_pdf: bool


class ValidationSchemaVersionSummary(BaseModel):
    id: str
    version_label: str
    status: str
    archived_at: str | None = None
    created_at: str | None = None


class ValidationSchemaGroupOut(BaseModel):
    schema_key: str
    versions: list[ValidationSchemaVersionSummary]


class ValidationSchemaVersionDetailOut(BaseModel):
    """Full persisted definition for one schema row (includes JSON ``body``)."""

    id: str
    schema_key: str
    version_label: str
    status: str
    body: dict[str, Any]
    created_at: str | None = None


class ValidationSchemaVersionCreate(BaseModel):
    """Create a new immutable schema revision.

    Omit ``version_label`` to let the server assign the next revision (e.g. ``1.0`` → ``1.1``).
    Omit ``body`` to use the built-in wine-quality M1 schema.
    """

    schema_key: str = Field(..., min_length=1, max_length=128)
    version_label: str | None = Field(default=None, max_length=64)
    body: dict[str, Any] | None = None
    archive_previous_active: bool = True