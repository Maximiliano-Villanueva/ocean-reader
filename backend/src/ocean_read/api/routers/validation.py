"""Schema-driven PDF validation — versioned rules + evidence-first responses."""

from __future__ import annotations

import uuid
from pathlib import PurePosixPath

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.exc import IntegrityError

from ocean_read.api.deps import SessionDep, ensure_under_upload_root, require_project, upload_root
from ocean_read.domain.validation.default_wine_schema import DEFAULT_WINE_QUALITY_SCHEMA_BODY
from ocean_read.domain.validation.lifecycle import can_use_for_validation
from ocean_read.domain.validation.revision import suggest_next_version_label
from ocean_read.domain.validation.pipeline_result import PipelineValidationResult
from ocean_read.infrastructure.persistence.validation_run_sqlalchemy import SqlAlchemyValidationRunRepository
from ocean_read.infrastructure.persistence.validation_schema_sqlalchemy import SqlAlchemyValidationSchemaRepository
from ocean_read.schemas import (
    AmbiguousFieldOut,
    FieldRuleOutcomeOut,
    ValidateDocumentResponse,
    ValidationEvidenceOut,
    ValidationFieldErrorOut,
    ValidationRunDetailOut,
    ValidationRunsPage,
    ValidationRunSummary,
    ValidationSchemaGroupOut,
    ValidationSchemaVersionCreate,
    ValidationSchemaVersionDetailOut,
    ValidationSchemaVersionSummary,
)
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
    return ValidateDocumentResponse(
        status=report.status,
        schema_id=schema_key,
        schema_version=version_label,
        results=results,
        ambiguous_fields=amb_out,
        schema_snapshot=report.schema_body_snapshot,
        resolved_values=report.resolved_values,
        field_rule_outcomes=fro_list,
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

    spec = body.body if body.body is not None else DEFAULT_WINE_QUALITY_SCHEMA_BODY
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
) -> ValidationRunsPage:
    """Paginated validation history (default & max page size: 25)."""

    await require_project(db, project_id)
    if page < 1:
        raise HTTPException(status_code=400, detail="page must be >= 1")
    ps = min(max(page_size, 1), _MAX_RUN_PAGE_SIZE)
    repo = SqlAlchemyValidationRunRepository(db)
    total = await repo.count_for_project(project_id)
    offset = (page - 1) * ps
    raw = await repo.list_page(project_id, limit=ps, offset=offset)
    items = [ValidationRunSummary.model_validate(r) for r in raw]
    return ValidationRunsPage(items=items, total=total, page=page, page_size=ps)


@router.get("/projects/{project_id}/validation-runs/{run_id}", response_model=ValidationRunDetailOut)
async def get_validation_run(project_id: uuid.UUID, run_id: uuid.UUID, db: SessionDep) -> ValidationRunDetailOut:
    await require_project(db, project_id)
    repo = SqlAlchemyValidationRunRepository(db)
    row = await repo.get(project_id, run_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Validation run not found")
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
    )


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
        pdf_relative_path=rel_path,
    )
    await db.commit()
    return final_response
