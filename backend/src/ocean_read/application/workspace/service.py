"""Use cases: workspace projects (validation shell)."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from ocean_read.application.ports.workspace import WorkspaceRepository
from ocean_read.db.models import Project
from ocean_read.domain.exceptions import ProjectNotFound
from ocean_read.domain.tenancy import DEFAULT_ORGANIZATION_ID
from ocean_read.domain.validation.default_wine_schema import (
    DEFAULT_WINE_QUALITY_SCHEMA_BODY,
    DEFAULT_WINE_SCHEMA_KEY,
    DEFAULT_WINE_VERSION_LABEL,
)

if TYPE_CHECKING:
    from ocean_read.application.ports.validation_schema_repository import ValidationSchemaRepository


class WorkspaceService:
    """Application service — orchestrates workspace behavior without HTTP or SQL details."""

    def __init__(
        self,
        repo: WorkspaceRepository,
        *,
        validation_schema_repo: ValidationSchemaRepository | None = None,
    ) -> None:
        self._repo = repo
        self._validation_schema_repo = validation_schema_repo

    async def create_project(self, name: str, *, organization_id: uuid.UUID | None = None) -> Project:
        oid = organization_id if organization_id is not None else DEFAULT_ORGANIZATION_ID
        # Primary-key default runs at INSERT flush time; seeding validation_schemas needs a stable FK now.
        p = Project(
            id=uuid.uuid4(),
            name=name,
            settings={"product": "validation"},
            organization_id=oid,
        )
        await self._repo.add_project(p)
        if self._validation_schema_repo is not None:
            await self._validation_schema_repo.create_version(
                project_id=p.id,
                schema_key=DEFAULT_WINE_SCHEMA_KEY,
                version_label=DEFAULT_WINE_VERSION_LABEL,
                body=DEFAULT_WINE_QUALITY_SCHEMA_BODY,
                archive_previous_active=False,
            )
        await self._repo.commit_refresh(p)
        return p

    async def list_projects(self) -> list[Project]:
        return await self._repo.list_projects()

    async def delete_project(self, project_id: uuid.UUID) -> None:
        p = await self._repo.get_project(project_id)
        if p is None:
            raise ProjectNotFound()
        await self._repo.delete_project_entity(p)
        await self._repo.commit_refresh()
