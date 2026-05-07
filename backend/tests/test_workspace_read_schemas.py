"""Regression: API response models accept SQLAlchemy ORM instances (Pydantic v2 from_attributes)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from ocean_read.db.models import Project
from ocean_read.schemas import ProjectRead


def _ts() -> datetime:
    return datetime.now(timezone.utc)


def test_project_read_serializes_from_orm() -> None:
    oid = UUID("00000000-0000-4000-8000-000000000001")
    p = Project(id=uuid4(), name="X", settings={}, organization_id=oid)
    p.created_at = _ts()
    p.updated_at = _ts()
    dto = ProjectRead.model_validate(p)
    assert dto.name == "X"
    assert dto.organization_id == oid
