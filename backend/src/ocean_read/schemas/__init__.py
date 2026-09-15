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
    by_field: dict[str, "ValidationEvidenceOut"] | None = Field(
        default=None,
        description="Cross-field rules: per-field evidence refs (each may include bbox).",
    )


ValidationEvidenceOut.model_rebuild()


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


class OpenEndedEvidenceOut(BaseModel):
    text: str = ""
    block_id: str = ""
    page: int = 1
    bbox: list[float] | None = None


class OpenEndedFieldResultOut(BaseModel):
    field: str
    extracted_value: str | None = None
    evaluation: Literal["pass", "fail", "ambiguous"] | None = None
    informative_only: bool = False
    evidence: list[OpenEndedEvidenceOut] = Field(default_factory=list)


class ValidateDocumentResponse(BaseModel):
    """Result of POST ``/api/validate-document`` — PASS / FAIL / AMBIGUOUS plus structured failures."""

    status: Literal["PASS", "FAIL", "AMBIGUOUS"]
    schema_id: str
    schema_version: str
    results: list[ValidationFieldErrorOut]
    ambiguous_fields: list[AmbiguousFieldOut] = Field(default_factory=list)
    open_ended_results: list[OpenEndedFieldResultOut] = Field(default_factory=list)
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
    extraction_meta: dict[str, Any] | None = Field(
        default=None,
        description="Extraction diagnostics, e.g. vision_fallback_used when page images were sent to the LLM.",
    )


class ValidationRunSummary(BaseModel):
    """One row in the validation history table."""

    id: str
    schema_key: str
    version_label: str
    document_filename: str
    outcome: str
    created_at: str | None = None
    archived_at: str | None = None
    deleted_at: str | None = None
    attributes: dict[str, str | None] = Field(
        default_factory=dict,
        description="User tags on this validation (key → value; null = key-only tag).",
    )


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
    pdf_hash: str = Field(default="", description="SHA-256 fingerprint of uploaded PDF bytes.")
    archived_at: str | None = None
    deleted_at: str | None = None
    parent_run_id: str | None = Field(
        default=None,
        description="When set, this run is a manual correction revision of the parent run.",
    )
    revision_number: int = Field(default=1, ge=1, description="1 for original extraction; increments on each save.")
    attributes: dict[str, str | None] = Field(default_factory=dict)


class CohortAttributeFilter(BaseModel):
    """Filter runs that have a tag key (and optional exact value)."""

    key: str = Field(..., min_length=1, max_length=64)
    value: str | None = Field(default=None, max_length=128)


class CohortFilters(BaseModel):
    """Criteria for grouping validations in the Insights tab."""

    schema_key: str | None = Field(default=None, max_length=128)
    version_label: str | None = Field(default=None, max_length=64)
    outcomes: list[str] = Field(default_factory=list, description="Empty = all outcomes.")
    attributes: list[CohortAttributeFilter] = Field(default_factory=list)


class ValidationCohortCreate(BaseModel):
    """Create a saved cohort view."""

    name: str = Field(..., min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=512)
    filters: CohortFilters = Field(default_factory=CohortFilters)
    pass_threshold_pct: float = Field(default=100.0, ge=0.0, le=100.0)


class ValidationCohortOut(BaseModel):
    """Saved cohort definition."""

    id: str
    name: str
    description: str | None = None
    filters: CohortFilters
    pass_threshold_pct: float
    created_at: str | None = None
    updated_at: str | None = None


class CohortEvaluationOut(BaseModel):
    """Aggregated stats + matching runs for a cohort."""

    total: int
    pass_count: int
    fail_count: int
    ambiguous_count: int
    pass_rate_pct: float
    pass_threshold_pct: float
    meets_threshold: bool
    items: list[ValidationRunSummary]


class ValidationAttributeVocabularyOut(BaseModel):
    """Known tag keys and values in a project (for upload autocomplete)."""

    keys: list[str]
    values_by_key: dict[str, list[str]]


class ValidationRunLifecyclePatch(BaseModel):
    """Update run visibility in history. ``restore`` clears both archive and soft-delete."""

    archived: bool | None = Field(
        default=None,
        description="True archives the run (hidden from default list); False clears archive only.",
    )
    restore: bool = Field(default=False, description="When true, clears archived_at and deleted_at.")


class ValidationRunLifecycleStateOut(BaseModel):
    """Lifecycle timestamps after PATCH (audit recovery)."""

    id: str
    archived_at: str | None = None
    deleted_at: str | None = None


class ValidationRunCorrectionCreate(BaseModel):
    """Human edits to extracted field values — creates a new run revision and revalidates."""

    corrections: dict[str, Any] = Field(
        ...,
        min_length=1,
        description="Map of field name → corrected value (numbers coerced per schema type).",
    )
    note: str | None = Field(default=None, max_length=2000, description="Optional audit note for this revision.")


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


class SuggestCrossFieldRuleIn(BaseModel):
    """Request body for M3 LLM-assisted cross-field rule drafting."""

    natural_language: str = Field(..., min_length=1, max_length=8000)
    allowed_field_names: list[str] = Field(
        ...,
        min_length=1,
        description="Top-level schema field names the expression may reference.",
    )


class SuggestCrossFieldRuleOut(BaseModel):
    """Validated suggestion ready to merge into ``cross_field_rules``."""

    id: str
    expression: str
    error_message: str


class SchemaAgentChatMessage(BaseModel):
    role: str
    content: str


class ValidateSchemaBodyIn(BaseModel):
    """Draft schema body for DSL validation (no PDF)."""

    body: dict[str, Any] = Field(default_factory=dict)


class ValidateSchemaBodyOut(BaseModel):
    ok: bool
    errors: list[str] = Field(default_factory=list)
    normalized_body: dict[str, Any] = Field(default_factory=dict)


class SchemaPreviewOut(BaseModel):
    """Temporary validation run for schema authoring (not persisted)."""

    dsl_ok: bool
    dsl_errors: list[str] = Field(default_factory=list)
    validation: ValidateDocumentResponse | None = None


class SchemaAgentValidationFeedback(BaseModel):
    """Structured feedback from studio DSL check and optional sample-PDF preview."""

    dsl_ok: bool = True
    dsl_errors: list[str] = Field(default_factory=list)
    preview_status: str | None = None
    preview_summary: str | None = Field(
        default=None,
        description="Human-readable summary for the authoring agent (resolved, missing, ambiguous, open-ended).",
    )
    judge_summary: str | None = Field(
        default=None,
        description="Schema judge agent critique (A2A) after preview.",
    )
    judge_recommendations: list[str] = Field(default_factory=list)


class SchemaJudgeAnalyzeIn(BaseModel):
    """Request schema judge critique after preview or DSL check."""

    schema_body: dict[str, Any] = Field(default_factory=dict)
    dsl_errors: list[str] = Field(default_factory=list)
    validation: ValidateDocumentResponse | None = None


class SchemaJudgeAnalyzeOut(BaseModel):
    summary: str
    recommendations: list[str] = Field(default_factory=list)
    priority: str = "medium"


class SchemaAgentChatIn(BaseModel):
    """Proxy to schema-agent service; includes current schema (user edits)."""

    messages: list[SchemaAgentChatMessage] = Field(default_factory=list)
    schema_body: dict[str, Any] = Field(default_factory=dict)
    sample_pdf_note: str | None = Field(
        default=None,
        description="Optional text summary when user attached a sample PDF for context.",
    )
    validation_feedback: SchemaAgentValidationFeedback | None = Field(
        default=None,
        description="Latest DSL / preview-run feedback so the agent can fix the draft.",
    )


class SchemaAgentChatOut(BaseModel):
    reply: str
    schema_body: dict[str, Any]


class SchemaAgentSamplePdfOut(BaseModel):
    """Text preview from a sample PDF for schema authoring context."""

    text_preview: str
    page_count: int
    block_count: int
