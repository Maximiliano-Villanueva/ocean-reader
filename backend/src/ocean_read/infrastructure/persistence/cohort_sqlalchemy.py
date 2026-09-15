"""SQLAlchemy adapter for validation cohorts (Insights tab)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ocean_read.db.models import ValidationCohort, ValidationRun
from ocean_read.domain.validation.cohort_aggregation import aggregate_outcomes, run_matches_cohort
from ocean_read.domain.validation.run_attributes import merge_attribute_vocabularies, normalize_run_attributes
from ocean_read.infrastructure.persistence.validation_run_sqlalchemy import _run_summary_dict


class SqlAlchemyCohortRepository:
    """CRUD for saved cohort views and attribute vocabulary."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_cohorts(self, project_id: uuid.UUID) -> list[dict[str, Any]]:
        q = await self._session.execute(
            select(ValidationCohort)
            .where(ValidationCohort.project_id == project_id)
            .order_by(ValidationCohort.created_at.desc())
        )
        return [_cohort_dict(row) for row in q.scalars().all()]

    async def get_cohort(self, project_id: uuid.UUID, cohort_id: uuid.UUID) -> dict[str, Any] | None:
        q = await self._session.execute(
            select(ValidationCohort).where(
                ValidationCohort.project_id == project_id,
                ValidationCohort.id == cohort_id,
            )
        )
        row = q.scalar_one_or_none()
        return _cohort_dict(row) if row else None

    async def insert_cohort(
        self,
        *,
        cohort_id: uuid.UUID,
        project_id: uuid.UUID,
        name: str,
        description: str | None,
        filters: dict[str, Any],
        pass_threshold_pct: float,
    ) -> uuid.UUID:
        row = ValidationCohort(
            id=cohort_id,
            project_id=project_id,
            name=name,
            description=description,
            filters=filters,
            pass_threshold_pct=pass_threshold_pct,
        )
        self._session.add(row)
        await self._session.flush()
        return cohort_id

    async def delete_cohort(self, project_id: uuid.UUID, cohort_id: uuid.UUID) -> bool:
        q = await self._session.execute(
            select(ValidationCohort).where(
                ValidationCohort.project_id == project_id,
                ValidationCohort.id == cohort_id,
            )
        )
        row = q.scalar_one_or_none()
        if row is None:
            return False
        await self._session.delete(row)
        return True

    async def list_visible_runs(self, project_id: uuid.UUID) -> list[dict[str, Any]]:
        """All non-archived, non-deleted runs for cohort evaluation."""

        q = await self._session.execute(
            select(ValidationRun)
            .where(
                ValidationRun.project_id == project_id,
                ValidationRun.archived_at.is_(None),
                ValidationRun.deleted_at.is_(None),
            )
            .order_by(ValidationRun.created_at.desc())
        )
        rows = q.scalars().all()
        out: list[dict[str, Any]] = []
        for row in rows:
            summary = _run_summary_dict(row)
            summary["attributes"] = dict(row.attributes or {})
            out.append(summary)
        return out

    async def evaluate_cohort(
        self,
        project_id: uuid.UUID,
        *,
        filters: dict[str, Any],
        pass_threshold_pct: float,
    ) -> dict[str, Any]:
        """Filter runs and return summary + matching items."""

        runs = await self.list_visible_runs(project_id)
        matched = [r for r in runs if run_matches_cohort(r, filters)]
        summary = aggregate_outcomes(matched, pass_threshold_pct=pass_threshold_pct)
        return {**summary, "items": matched}

    async def attribute_vocabulary(self, project_id: uuid.UUID) -> dict[str, list[str]]:
        """Collect known attribute keys and values from all visible runs."""

        runs = await self.list_visible_runs(project_id)
        vocab: dict[str, set[str]] = {}
        for run in runs:
            attrs = normalize_run_attributes(run.get("attributes"))
            for key, value in attrs.items():
                vocab.setdefault(key, set())
                if value:
                    vocab[key].add(value)
        return merge_attribute_vocabularies(vocab, {})


def _cohort_dict(row: ValidationCohort) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "project_id": str(row.project_id),
        "name": row.name,
        "description": row.description,
        "filters": dict(row.filters or {}),
        "pass_threshold_pct": float(row.pass_threshold_pct),
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }
