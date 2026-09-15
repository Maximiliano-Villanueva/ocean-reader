"""Insights tab — saved cohort views and aggregated validation statistics."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status

from ocean_read.api.deps import SessionDep, require_project
from ocean_read.infrastructure.persistence.cohort_sqlalchemy import SqlAlchemyCohortRepository
from ocean_read.schemas import (
    CohortEvaluationOut,
    CohortFilters,
    ValidationAttributeVocabularyOut,
    ValidationCohortCreate,
    ValidationCohortOut,
    ValidationRunSummary,
)

router = APIRouter(tags=["Insights"])


@router.get(
    "/projects/{project_id}/validation-attributes",
    response_model=ValidationAttributeVocabularyOut,
)
async def get_validation_attribute_vocabulary(
    project_id: uuid.UUID,
    db: SessionDep,
) -> ValidationAttributeVocabularyOut:
    """List tag keys and values already used in this project."""

    await require_project(db, project_id)
    repo = SqlAlchemyCohortRepository(db)
    vocab = await repo.attribute_vocabulary(project_id)
    return ValidationAttributeVocabularyOut(
        keys=sorted(vocab.keys()),
        values_by_key=vocab,
    )


@router.get("/projects/{project_id}/validation-cohorts", response_model=list[ValidationCohortOut])
async def list_validation_cohorts(project_id: uuid.UUID, db: SessionDep) -> list[ValidationCohortOut]:
    """List saved cohort views for the Insights tab."""

    await require_project(db, project_id)
    repo = SqlAlchemyCohortRepository(db)
    rows = await repo.list_cohorts(project_id)
    return [_cohort_out(row) for row in rows]


@router.post(
    "/projects/{project_id}/validation-cohorts",
    response_model=ValidationCohortOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_validation_cohort(
    project_id: uuid.UUID,
    body: ValidationCohortCreate,
    db: SessionDep,
) -> ValidationCohortOut:
    """Create a saved cohort view."""

    await require_project(db, project_id)
    repo = SqlAlchemyCohortRepository(db)
    cohort_id = uuid.uuid4()
    filters = body.filters.model_dump()
    await repo.insert_cohort(
        cohort_id=cohort_id,
        project_id=project_id,
        name=body.name.strip(),
        description=body.description.strip() if body.description else None,
        filters=filters,
        pass_threshold_pct=body.pass_threshold_pct,
    )
    await db.commit()
    row = await repo.get_cohort(project_id, cohort_id)
    if row is None:
        raise HTTPException(status_code=500, detail="Failed to load created cohort")
    return _cohort_out(row)


@router.delete("/projects/{project_id}/validation-cohorts/{cohort_id}", status_code=status.HTTP_200_OK)
async def delete_validation_cohort(
    project_id: uuid.UUID,
    cohort_id: uuid.UUID,
    db: SessionDep,
) -> dict[str, str]:
    """Remove a saved cohort view."""

    await require_project(db, project_id)
    repo = SqlAlchemyCohortRepository(db)
    ok = await repo.delete_cohort(project_id, cohort_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Cohort not found")
    await db.commit()
    return {"status": "deleted"}


@router.get(
    "/projects/{project_id}/validation-cohorts/{cohort_id}/evaluate",
    response_model=CohortEvaluationOut,
)
async def evaluate_saved_cohort(
    project_id: uuid.UUID,
    cohort_id: uuid.UUID,
    db: SessionDep,
) -> CohortEvaluationOut:
    """Evaluate a saved cohort and return aggregated stats."""

    await require_project(db, project_id)
    repo = SqlAlchemyCohortRepository(db)
    cohort = await repo.get_cohort(project_id, cohort_id)
    if cohort is None:
        raise HTTPException(status_code=404, detail="Cohort not found")
    result = await repo.evaluate_cohort(
        project_id,
        filters=cohort["filters"],
        pass_threshold_pct=float(cohort["pass_threshold_pct"]),
    )
    return _evaluation_out(result)


@router.post(
    "/projects/{project_id}/validation-cohorts/evaluate",
    response_model=CohortEvaluationOut,
)
async def evaluate_ad_hoc_cohort(
    project_id: uuid.UUID,
    body: ValidationCohortCreate,
    db: SessionDep,
) -> CohortEvaluationOut:
    """Preview cohort stats without saving (ad-hoc filters)."""

    await require_project(db, project_id)
    repo = SqlAlchemyCohortRepository(db)
    result = await repo.evaluate_cohort(
        project_id,
        filters=body.filters.model_dump(),
        pass_threshold_pct=body.pass_threshold_pct,
    )
    return _evaluation_out(result)


def _cohort_out(row: dict) -> ValidationCohortOut:
    return ValidationCohortOut(
        id=row["id"],
        name=row["name"],
        description=row.get("description"),
        filters=CohortFilters.model_validate(row.get("filters") or {}),
        pass_threshold_pct=float(row.get("pass_threshold_pct") or 100.0),
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
    )


def _evaluation_out(result: dict) -> CohortEvaluationOut:
    items = [ValidationRunSummary.model_validate(item) for item in result.get("items", [])]
    return CohortEvaluationOut(
        total=int(result["total"]),
        pass_count=int(result["pass_count"]),
        fail_count=int(result["fail_count"]),
        ambiguous_count=int(result["ambiguous_count"]),
        pass_rate_pct=float(result["pass_rate_pct"]),
        pass_threshold_pct=float(result["pass_threshold_pct"]),
        meets_threshold=bool(result["meets_threshold"]),
        items=items,
    )
