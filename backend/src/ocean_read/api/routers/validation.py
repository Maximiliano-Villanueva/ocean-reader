"""Schema-driven PDF validation — versioned rules + evidence-first responses."""

from __future__ import annotations

import json
import uuid
from pathlib import PurePosixPath
from typing import Any

import httpx
from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.exc import IntegrityError

from ocean_read.api.deps import SessionDep, ensure_under_upload_root, require_project, upload_root
from ocean_read.config import get_settings
from ocean_read.domain.validation.default_wine_schema import DEFAULT_WINE_QUALITY_SCHEMA_BODY
from ocean_read.domain.validation.lifecycle import can_use_for_validation
from ocean_read.domain.validation.revision import suggest_next_version_label
from ocean_read.domain.validation.run_attributes import normalize_run_attributes
from ocean_read.domain.validation.run_manual_revision import apply_manual_field_corrections
from ocean_read.domain.validation.pipeline_result import PipelineValidationResult
from ocean_read.domain.validation.schema_dsl import collect_schema_dsl_errors
from ocean_read.domain.validation.schema_normalizer import normalize_schema_body, schema_has_open_ended
from ocean_read.domain.validation.schema_expression_assist import suggest_cross_field_rule_from_nl
from ocean_read.infrastructure.persistence.validation_run_sqlalchemy import SqlAlchemyValidationRunRepository
from ocean_read.infrastructure.persistence.validation_schema_sqlalchemy import SqlAlchemyValidationSchemaRepository
from ocean_read.providers.ollama import OllamaLLMClient
from ocean_read.schemas import (
    AmbiguousFieldOut,
    FieldRuleOutcomeOut,
    SuggestCrossFieldRuleIn,
    SuggestCrossFieldRuleOut,
    ValidateDocumentResponse,
    ValidationEvidenceOut,
    ValidationFieldErrorOut,
    ValidationRunCorrectionCreate,
    ValidationRunDetailOut,
    ValidationRunLifecyclePatch,
    ValidationRunLifecycleStateOut,
    ValidationRunsPage,
    ValidationRunSummary,
    ValidationSchemaGroupOut,
    ValidationSchemaVersionCreate,
    ValidationSchemaVersionDetailOut,
    ValidationSchemaVersionSummary,
    SchemaAgentChatIn,
    SchemaAgentChatOut,
    SchemaAgentSamplePdfOut,
    SchemaJudgeAnalyzeIn,
    SchemaJudgeAnalyzeOut,
    SchemaPreviewOut,
    ValidateSchemaBodyIn,
    ValidateSchemaBodyOut,
)
from ocean_read.services.schema_judge import _fallback_feedback, analyze_preview_for_authoring
from ocean_read.domain.validation.pdf_blocks import parse_pdf_blocks
from ocean_read.services.validation_pipeline import run_wine_pdf_validation

router = APIRouter(tags=["Validation"])

# Validation uploads are ephemeral (not stored as corpus); keep a sane upper bound.
_MAX_VALIDATE_BYTES = 30 * 1024 * 1024

_MAX_RUN_PAGE_SIZE = 25


def _report_to_response(report: PipelineValidationResult, schema_key: str, version_label: str) -> ValidateDocumentResponse:
    results: list[ValidationFieldErrorOut] = []
    for e in report.errors:
        ev_out: ValidationEvidenceOut | None = None
        if e.evidence:
            ev_out = ValidationEvidenceOut.model_validate(e.evidence)
        results.append(
            ValidationFieldErrorOut(
                field=e.field,
                value=e.value,
                expected=e.expected,
                rule=e.rule,
                evidence=ev_out,
            )
        )
    amb_out = [
        AmbiguousFieldOut(field=a.field, candidate_count=a.count) for a in report.ambiguous_fields
    ]
    fro_list: list[FieldRuleOutcomeOut] = []
    for o in report.field_rule_outcomes:
        ev_rule: ValidationEvidenceOut | None = None
        if o.evidence:
            ev_rule = ValidationEvidenceOut.model_validate(o.evidence)
        fro_list.append(
            FieldRuleOutcomeOut(
                field=o.field,
                rule=o.rule,
                passed=o.passed,
                value=o.value,
                expected=o.expected,
                evidence=ev_rule,
            )
        )
    from ocean_read.schemas import OpenEndedEvidenceOut, OpenEndedFieldResultOut

    oe_out: list[OpenEndedFieldResultOut] = []
    for oe in report.open_ended_results:
        oe_out.append(
            OpenEndedFieldResultOut(
                field=oe.field,
                extracted_value=oe.extracted_value,
                evaluation=oe.evaluation,
                informative_only=oe.informative_only,
                evidence=[
                    OpenEndedEvidenceOut(
                        text=e.text,
                        block_id=e.block_id,
                        page=e.page,
                        bbox=e.bbox,
                    )
                    for e in oe.evidence
                ],
            )
        )
    extraction_meta = None
    if report.pipeline_snapshots:
        raw_meta = report.pipeline_snapshots.get("extraction_meta")
        if isinstance(raw_meta, dict):
            extraction_meta = raw_meta
    return ValidateDocumentResponse(
        status=report.status,
        schema_id=schema_key,
        schema_version=version_label,
        results=results,
        ambiguous_fields=amb_out,
        schema_snapshot=report.schema_body_snapshot,
        resolved_values=report.resolved_values,
        field_rule_outcomes=fro_list,
        open_ended_results=oe_out,
        extraction_meta=extraction_meta,
    )


@router.get("/projects/{project_id}/validation-schemas", response_model=list[ValidationSchemaGroupOut])
async def list_validation_schemas(project_id: uuid.UUID, db: SessionDep) -> list[ValidationSchemaGroupOut]:
    await require_project(db, project_id)
    repo = SqlAlchemyValidationSchemaRepository(db)
    raw = await repo.list_grouped_by_project(project_id)
    out: list[ValidationSchemaGroupOut] = []
    for g in raw:
        versions = [ValidationSchemaVersionSummary.model_validate(v) for v in g["versions"]]
        out.append(ValidationSchemaGroupOut(schema_key=g["schema_key"], versions=versions))
    return out


@router.get(
    "/projects/{project_id}/validation-schemas/{schema_id}",
    response_model=ValidationSchemaVersionDetailOut,
)
async def get_validation_schema_version(
    project_id: uuid.UUID,
    schema_id: uuid.UUID,
    db: SessionDep,
) -> ValidationSchemaVersionDetailOut:
    """Return one schema row including the JSON ``body`` (fields + rules) for viewing or fork-edit."""

    await require_project(db, project_id)
    repo = SqlAlchemyValidationSchemaRepository(db)
    row = await repo.get_by_id(schema_id)
    if row is None or row["project_id"] != project_id:
        raise HTTPException(status_code=404, detail="Validation schema version not found")
    return ValidationSchemaVersionDetailOut(
        id=row["id"],
        schema_key=row["schema_key"],
        version_label=row["version_label"],
        status=row["status"],
        body=row["body"],
        created_at=row.get("created_at"),
    )


@router.post(
    "/projects/{project_id}/validation-schemas/suggest-cross-field-rule",
    response_model=SuggestCrossFieldRuleOut,
)
async def suggest_cross_field_rule(
    project_id: uuid.UUID,
    body: SuggestCrossFieldRuleIn,
    db: SessionDep,
) -> SuggestCrossFieldRuleOut:
    """M3: draft a ``cross_field_rules`` entry from natural language via Ollama (temperature 0).

    Disabled unless ``VALIDATION_SCHEMA_LLM_ASSIST_ENABLED`` is true. Output is validated
    (identifiers ⊆ allow-list, expression parses and evaluates as boolean with dummy numbers).
    """

    await require_project(db, project_id)
    if not get_settings().validation_schema_llm_assist_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Schema expression assist is disabled (set VALIDATION_SCHEMA_LLM_ASSIST_ENABLED=true).",
        )
    names = sorted({str(x).strip() for x in body.allowed_field_names if str(x).strip()})
    if not names:
        raise HTTPException(status_code=400, detail="allowed_field_names must be non-empty")
    llm = OllamaLLMClient()
    try:
        try:
            out = await suggest_cross_field_rule_from_nl(
                natural_language=body.natural_language,
                allowed_field_names=names,
                client=llm,
            )
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    finally:
        await llm.aclose()
    return SuggestCrossFieldRuleOut(**out)


@router.delete("/projects/{project_id}/validation-schemas/{schema_id}")
async def delete_validation_schema_version(
    project_id: uuid.UUID,
    schema_id: uuid.UUID,
    db: SessionDep,
) -> dict[str, str]:
    """Soft-delete one immutable schema version row (key + version label)."""

    await require_project(db, project_id)
    repo = SqlAlchemyValidationSchemaRepository(db)
    row = await repo.get_by_id(schema_id)
    if row is None or row["project_id"] != project_id:
        raise HTTPException(status_code=404, detail="Validation schema version not found")
    await repo.soft_delete(schema_id)
    await db.commit()
    return {"status": "deleted"}


@router.post(
    "/projects/{project_id}/validation-schemas",
    response_model=ValidationSchemaVersionSummary,
    status_code=status.HTTP_201_CREATED,
)
async def create_validation_schema_version(
    project_id: uuid.UUID,
    body: ValidationSchemaVersionCreate,
    db: SessionDep,
) -> ValidationSchemaVersionSummary:
    """Persist a new immutable revision. Omit ``version_label`` for auto label; omit ``body`` for wine defaults."""

    await require_project(db, project_id)
    sk = body.schema_key.strip()
    if not sk:
        raise HTTPException(status_code=400, detail="schema_key must be non-empty")

    repo = SqlAlchemyValidationSchemaRepository(db)
    sv_raw = (body.version_label or "").strip()
    if sv_raw:
        sv = sv_raw
    else:
        existing = await repo.list_versions(project_id, sk)
        labels = [str(x["version_label"]) for x in existing]
        sv = suggest_next_version_label(labels)

    spec = normalize_schema_body(body.body if body.body is not None else DEFAULT_WINE_QUALITY_SCHEMA_BODY)
    dsl_errors = collect_schema_dsl_errors(spec)
    if dsl_errors:
        raise HTTPException(status_code=400, detail={"schema_dsl_errors": dsl_errors})
    try:
        await repo.create_version(
            project_id=project_id,
            schema_key=sk,
            version_label=sv,
            body=spec,
            archive_previous_active=body.archive_previous_active,
        )
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail="A schema with this schema_key and version_label already exists for this project.",
        ) from exc

    row = await repo.get_by_version(project_id, sk, sv)
    if row is None:
        raise HTTPException(status_code=500, detail="Schema row missing after insert")
    return ValidationSchemaVersionSummary(
        id=row["id"],
        version_label=row["version_label"],
        status=row["status"],
        archived_at=None,
        created_at=row.get("created_at"),
    )


@router.get("/projects/{project_id}/validation-runs", response_model=ValidationRunsPage)
async def list_validation_runs(
    project_id: uuid.UUID,
    db: SessionDep,
    page: int = 1,
    page_size: int = 25,
    schema_key: str | None = Query(None, max_length=128),
    version_label: str | None = Query(None, max_length=64, description="Filter by schema revision label (e.g. 1.0)"),
    document_contains: str | None = Query(
        None,
        max_length=256,
        description="Case-insensitive substring match on stored document filename",
    ),
    status: str | None = Query(None, max_length=32, description="Filter by outcome (PASS, FAIL, AMBIGUOUS)"),
    include_hidden: bool = Query(
        False,
        description="When true, include archived and soft-deleted runs (default list hides them).",
    ),
) -> ValidationRunsPage:
    """Paginated validation history (default & max page size: 25)."""

    await require_project(db, project_id)
    if page < 1:
        raise HTTPException(status_code=400, detail="page must be >= 1")
    ps = min(max(page_size, 1), _MAX_RUN_PAGE_SIZE)
    repo = SqlAlchemyValidationRunRepository(db)
    sk = schema_key.strip() if schema_key else None
    vl = version_label.strip() if version_label else None
    doc_q = document_contains.strip() if document_contains else None
    st = status.strip() if status else None
    total = await repo.count_for_project(
        project_id,
        schema_key=sk,
        version_label=vl,
        outcome=st,
        document_contains=doc_q,
        include_hidden=include_hidden,
    )
    offset = (page - 1) * ps
    raw = await repo.list_page(
        project_id,
        limit=ps,
        offset=offset,
        schema_key=sk,
        version_label=vl,
        outcome=st,
        document_contains=doc_q,
        include_hidden=include_hidden,
    )
    items = [ValidationRunSummary.model_validate(r) for r in raw]
    return ValidationRunsPage(items=items, total=total, page=page, page_size=ps)


def _run_detail_from_row(row: dict[str, Any]) -> ValidationRunDetailOut:
  rep = ValidateDocumentResponse.model_validate(row["report"])
  return ValidationRunDetailOut(
      id=row["id"],
      schema_key=row["schema_key"],
      version_label=row["version_label"],
      document_filename=row["document_filename"],
      outcome=row["outcome"],
      created_at=row["created_at"],
      report=rep,
      has_pdf=bool(row["pdf_relative_path"]),
      pdf_hash=row["pdf_hash"],
      archived_at=row.get("archived_at"),
      deleted_at=row.get("deleted_at"),
      parent_run_id=row.get("parent_run_id"),
      revision_number=int(row.get("revision_number") or 1),
      attributes=dict(row.get("attributes") or {}),
  )


@router.get("/projects/{project_id}/validation-runs/{run_id}", response_model=ValidationRunDetailOut)
async def get_validation_run(project_id: uuid.UUID, run_id: uuid.UUID, db: SessionDep) -> ValidationRunDetailOut:
    await require_project(db, project_id)
    repo = SqlAlchemyValidationRunRepository(db)
    row = await repo.get(project_id, run_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Validation run not found")
    return _run_detail_from_row(row)


@router.post(
    "/projects/{project_id}/validation-runs/{run_id}/revisions",
    response_model=ValidationRunDetailOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_validation_run_revision(
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    body: ValidationRunCorrectionCreate,
    db: SessionDep,
) -> ValidationRunDetailOut:
    """Save human field corrections as a new run revision and revalidate PASS/FAIL/AMBIGUOUS."""

    await require_project(db, project_id)
    repo = SqlAlchemyValidationRunRepository(db)
    parent = await repo.get(project_id, run_id)
    if parent is None:
        raise HTTPException(status_code=404, detail="Validation run not found")

    try:
        updated_report = apply_manual_field_corrections(dict(parent["report"]), body.corrections)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if body.note:
        updated_report["revision_note"] = body.note.strip()

    new_run_id = uuid.uuid4()
    updated_report["run_id"] = str(new_run_id)
    parent_revision = int(parent.get("revision_number") or 1)

    if parent.get("validation_schema_id"):
        try:
            schema_uuid = uuid.UUID(str(parent["validation_schema_id"]))
        except ValueError:
            schema_uuid = None
    else:
        schema_uuid = None

    await repo.insert(
        run_id=new_run_id,
        project_id=project_id,
        validation_schema_id=schema_uuid,
        schema_key=parent["schema_key"],
        version_label=parent["version_label"],
        document_filename=parent["document_filename"],
        outcome=str(updated_report["status"]),
        report=updated_report,
        pdf_hash=parent["pdf_hash"],
        snapshots=parent.get("snapshots"),
        pdf_relative_path=parent.get("pdf_relative_path"),
        parent_run_id=run_id,
        revision_number=parent_revision + 1,
        attributes=dict(parent.get("attributes") or {}),
    )
    await db.commit()

    created = await repo.get(project_id, new_run_id)
    if created is None:
        raise HTTPException(status_code=500, detail="Failed to load created revision")
    return _run_detail_from_row(created)


@router.patch(
    "/projects/{project_id}/validation-runs/{run_id}",
    response_model=ValidationRunLifecycleStateOut,
)
async def patch_validation_run_lifecycle(
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    body: ValidationRunLifecyclePatch,
    db: SessionDep,
) -> ValidationRunLifecycleStateOut:
    """Archive, unarchive, or restore a run (audit recovery — row remains in DB)."""

    await require_project(db, project_id)
    repo = SqlAlchemyValidationRunRepository(db)
    existing = await repo.get(project_id, run_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Validation run not found")
    if body.restore:
        await repo.restore(project_id, run_id)
    elif body.archived is not None:
        ok = await repo.set_archived(project_id, run_id, archived=body.archived)
        if not ok:
            raise HTTPException(status_code=404, detail="Validation run not found")
    else:
        raise HTTPException(
            status_code=400,
            detail="Provide restore=true or archived (true to archive, false to unarchive).",
        )
    await db.commit()
    state = await repo.get_lifecycle_state(project_id, run_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Validation run not found")
    return ValidationRunLifecycleStateOut(id=str(run_id), **state)


@router.delete("/projects/{project_id}/validation-runs/{run_id}")
async def soft_delete_validation_run(
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    db: SessionDep,
) -> dict[str, str]:
    """Soft-delete a validation run (hidden from default history; recover via PATCH restore)."""

    await require_project(db, project_id)
    repo = SqlAlchemyValidationRunRepository(db)
    existing = await repo.get(project_id, run_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Validation run not found")
    await repo.soft_delete(project_id, run_id)
    await db.commit()
    return {"status": "deleted"}


@router.get(
    "/projects/{project_id}/validation-runs/{run_id}/blocks",
    response_model=list[dict[str, Any]],
)
async def get_validation_run_blocks(
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    db: SessionDep,
) -> list[dict[str, Any]]:
    """Persisted layout blocks for this run (M2 pipeline snapshot)."""

    await require_project(db, project_id)
    repo = SqlAlchemyValidationRunRepository(db)
    row = await repo.get(project_id, run_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Validation run not found")
    snaps = row.get("snapshots") or {}
    blocks = snaps.get("blocks")
    if blocks is None:
        return []
    return list(blocks)


@router.get(
    "/projects/{project_id}/validation-runs/{run_id}/candidates",
    response_model=list[dict[str, Any]],
)
async def get_validation_run_candidates(
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    db: SessionDep,
) -> list[dict[str, Any]]:
    """All extraction candidates recorded for this run."""

    await require_project(db, project_id)
    repo = SqlAlchemyValidationRunRepository(db)
    row = await repo.get(project_id, run_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Validation run not found")
    snaps = row.get("snapshots") or {}
    cands = snaps.get("candidates")
    if cands is None:
        return []
    return list(cands)


@router.get(
    "/projects/{project_id}/validation-runs/{run_id}/resolved",
    response_model=dict[str, Any],
)
async def get_validation_run_resolved(
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    db: SessionDep,
) -> dict[str, Any]:
    """Resolved field values after deterministic tie-break (empty if ambiguous-only snapshot)."""

    await require_project(db, project_id)
    repo = SqlAlchemyValidationRunRepository(db)
    row = await repo.get(project_id, run_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Validation run not found")
    snaps = row.get("snapshots") or {}
    resolved = snaps.get("resolved_document")
    if resolved is None:
        return {}
    return dict(resolved)


@router.get("/projects/{project_id}/validation-runs/{run_id}/document")
async def get_validation_run_document(
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    db: SessionDep,
) -> FileResponse:
    """Serve the PDF stored with a validation run (same bytes as the original upload)."""

    await require_project(db, project_id)
    repo = SqlAlchemyValidationRunRepository(db)
    row = await repo.get(project_id, run_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Validation run not found")
    rel = row["pdf_relative_path"]
    if not rel:
        raise HTTPException(status_code=404, detail="No PDF stored for this run")
    root = upload_root()
    full = (root / rel).resolve()
    ensure_under_upload_root(full)
    if not full.is_file():
        raise HTTPException(status_code=404, detail="PDF file missing on disk")
    return FileResponse(
        path=str(full),
        media_type="application/pdf",
        filename=row["document_filename"],
    )


@router.post("/validate-document", response_model=ValidateDocumentResponse)
async def validate_document(
    db: SessionDep,
    project_id: uuid.UUID = Form(...),
    schema_id: str = Form(...),
    schema_version: str = Form(...),
    document: UploadFile = File(...),
    attributes: str | None = Form(
        default=None,
        description='Optional JSON object or list of {"key","value"} tags for this validation.',
    ),
) -> ValidateDocumentResponse:
    """Run PDF → extraction → resolution → validation for one persisted schema version."""

    await require_project(db, project_id)
    sk = schema_id.strip()
    sv = schema_version.strip()
    if not sk or not sv:
        raise HTTPException(status_code=400, detail="schema_id and schema_version are required")

    repo = SqlAlchemyValidationSchemaRepository(db)
    row = await repo.get_by_version(project_id, sk, sv)
    if row is None:
        raise HTTPException(status_code=404, detail="Validation schema version not found")
    if not can_use_for_validation(row["status"]):
        raise HTTPException(status_code=409, detail="Schema version is not active")

    data = await document.read()
    if len(data) > _MAX_VALIDATE_BYTES:
        raise HTTPException(status_code=413, detail="PDF exceeds validation size limit")

    mime = (document.content_type or "").lower()
    name = (document.filename or "").lower()
    if "pdf" not in mime and not name.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Expected application/pdf")

    run_attributes: dict[str, str | None] = {}
    if attributes and attributes.strip():
        try:
            parsed_attrs = json.loads(attributes)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail="attributes must be valid JSON") from exc
        run_attributes = normalize_run_attributes(parsed_attrs)

    report = await run_wine_pdf_validation(
        data,
        schema_body=row["body"],
        schema_key=sk,
        version_label=sv,
    )
    response = _report_to_response(report, sk, sv)
    run_id = uuid.uuid4()
    final_response = response.model_copy(update={"run_id": str(run_id)})

    schema_uuid = uuid.UUID(str(row["id"]))
    safe_name = PurePosixPath(document.filename or "document.pdf").name
    run_repo = SqlAlchemyValidationRunRepository(db)

    rel_path: str | None = None
    try:
        root = upload_root()
        dest = root / str(project_id) / "validation_runs" / f"{run_id}.pdf"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        rel_path = str(dest.relative_to(root))
    except OSError:
        rel_path = None

    await run_repo.insert(
        run_id=run_id,
        project_id=project_id,
        validation_schema_id=schema_uuid,
        schema_key=sk,
        version_label=sv,
        document_filename=safe_name,
        outcome=final_response.status,
        report=final_response.model_dump(),
        pdf_hash=report.pdf_hash,
        snapshots=report.pipeline_snapshots,
        pdf_relative_path=rel_path,
        attributes=run_attributes,
    )
    await db.commit()
    return final_response


@router.post(
    "/projects/{project_id}/validation-schemas/validate-body",
    response_model=ValidateSchemaBodyOut,
    tags=["Validation", "Schema authoring"],
)
async def validate_schema_body_for_project(
    project_id: uuid.UUID,
    payload: ValidateSchemaBodyIn,
    db: SessionDep,
) -> ValidateSchemaBodyOut:
    """DSL validation for draft schemas in Schema Studio (no version row required)."""

    await require_project(db, project_id)
    normalized = normalize_schema_body(payload.body)
    errs = collect_schema_dsl_errors(normalized)
    return ValidateSchemaBodyOut(ok=not errs, errors=errs, normalized_body=normalized)


def _preview_feedback_summary(response: ValidateDocumentResponse) -> str:
    """Compact text for the schema authoring agent."""

    lines: list[str] = [f"Outcome: {response.status}"]
    if response.resolved_values:
        resolved = ", ".join(f"{k}={v!r}" for k, v in sorted(response.resolved_values.items()))
        lines.append(f"Resolved: {resolved}")
    if response.results:
        fails = ", ".join(f"{e.field} ({e.rule})" for e in response.results)
        lines.append(f"Validation failures: {fails}")
    if response.ambiguous_fields:
        amb = ", ".join(f"{a.field} ({a.candidate_count} candidates)" for a in response.ambiguous_fields)
        lines.append(f"Ambiguous: {amb}")
    if response.open_ended_results:
        oe_parts: list[str] = []
        for oe in response.open_ended_results:
            tag = oe.evaluation or "no evaluation"
            if oe.informative_only:
                tag = f"informative: {oe.extracted_value!r}"
            oe_parts.append(f"{oe.field}={tag}")
        lines.append(f"Open-ended: {'; '.join(oe_parts)}")
    return "\n".join(lines)


@router.post(
    "/projects/{project_id}/validation-schemas/preview",
    response_model=SchemaPreviewOut,
    tags=["Validation", "Schema authoring"],
)
async def preview_validation_on_draft(
    project_id: uuid.UUID,
    db: SessionDep,
    document: UploadFile = File(...),
    schema_body: str = Form(...),
) -> SchemaPreviewOut:
    """Run the full validation pipeline on a draft schema + sample PDF without persisting a run."""

    await require_project(db, project_id)
    try:
        raw_body = json.loads(schema_body)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"schema_body must be valid JSON: {exc}") from exc
    if not isinstance(raw_body, dict):
        raise HTTPException(status_code=400, detail="schema_body must be a JSON object")

    normalized = normalize_schema_body(raw_body)
    dsl_errors = collect_schema_dsl_errors(normalized)
    if dsl_errors:
        return SchemaPreviewOut(dsl_ok=False, dsl_errors=dsl_errors, validation=None)

    data = await document.read()
    if len(data) > _MAX_VALIDATE_BYTES:
        raise HTTPException(status_code=413, detail="PDF exceeds validation size limit")
    mime = (document.content_type or "").lower()
    name = (document.filename or "").lower()
    if "pdf" not in mime and not name.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Expected application/pdf")

    report = await run_wine_pdf_validation(
        data,
        schema_body=normalized,
        schema_key="preview",
        version_label="draft",
    )
    validation = _report_to_response(report, "preview", "draft")
    return SchemaPreviewOut(dsl_ok=True, dsl_errors=[], validation=validation)


@router.post(
    "/projects/{project_id}/schema-judge/analyze",
    response_model=SchemaJudgeAnalyzeOut,
    tags=["Validation", "Schema authoring"],
)
async def schema_judge_analyze(
    project_id: uuid.UUID,
    payload: SchemaJudgeAnalyzeIn,
    db: SessionDep,
) -> SchemaJudgeAnalyzeOut:
    """LLM judge critique of a draft schema + optional preview run (feeds schema agent A2A loop)."""

    await require_project(db, project_id)
    settings = get_settings()
    normalized = normalize_schema_body(payload.schema_body)
    validation_dict = payload.validation.model_dump() if payload.validation else None
    if settings.validation_schema_judge_enabled:
        raw = await analyze_preview_for_authoring(
            schema_body=normalized,
            validation=validation_dict,
            dsl_errors=list(payload.dsl_errors),
        )
        return SchemaJudgeAnalyzeOut.model_validate(raw)
    raw = _fallback_feedback(
        schema_body=normalized,
        validation=validation_dict,
        dsl_errors=list(payload.dsl_errors),
    )
    return SchemaJudgeAnalyzeOut.model_validate(raw)


@router.post(
    "/projects/{project_id}/schema-agent/chat",
    response_model=SchemaAgentChatOut,
    tags=["Validation", "Schema agent"],
)
async def schema_agent_chat(project_id: uuid.UUID, payload: SchemaAgentChatIn, db: SessionDep) -> SchemaAgentChatOut:
    """Forward chat + current schema draft to the ADK schema-agent service (stateless)."""

    await require_project(db, project_id)
    settings = get_settings()
    url = f"{settings.schema_agent_url.rstrip('/')}/chat"
    body = {
        "messages": [m.model_dump() for m in payload.messages],
        "schema_body": payload.schema_body,
        "sample_pdf_note": payload.sample_pdf_note,
        "validation_feedback": payload.validation_feedback.model_dump() if payload.validation_feedback else None,
    }
    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            r = await client.post(url, json=body)
            if r.status_code >= 400:
                detail = r.text[:500]
                try:
                    payload = r.json()
                    if isinstance(payload, dict) and payload.get("detail"):
                        detail = str(payload["detail"])
                except Exception:
                    pass
                raise HTTPException(
                    status.HTTP_502_BAD_GATEWAY if r.status_code == 502 else r.status_code,
                    detail=detail,
                )
            data = r.json()
    except HTTPException:
        raise
    except httpx.HTTPError as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail=f"Schema agent unavailable at {url}: {exc}",
        ) from exc
    return SchemaAgentChatOut.model_validate(data)


@router.post(
    "/projects/{project_id}/schema-agent/sample-pdf-text",
    response_model=SchemaAgentSamplePdfOut,
    tags=["Validation", "Schema agent"],
)
async def schema_agent_sample_pdf_text(
    project_id: uuid.UUID,
    db: SessionDep,
    document: UploadFile = File(...),
) -> SchemaAgentSamplePdfOut:
    """Extract layout text from an optional sample PDF for agent context (not stored)."""

    await require_project(db, project_id)
    data = await document.read()
    if len(data) > _MAX_VALIDATE_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="PDF too large")
    blocks = parse_pdf_blocks(data)
    pages = {b.page for b in blocks}
    lines: list[str] = []
    for b in blocks[:100]:
        lines.append(f"[p{b.page} #{b.id}] {(b.text or '').strip()}")
    preview = "\n".join(lines)[:14000]
    return SchemaAgentSamplePdfOut(
        text_preview=preview,
        page_count=max(pages) if pages else 0,
        block_count=len(blocks),
    )
