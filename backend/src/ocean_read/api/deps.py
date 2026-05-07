"""FastAPI/shared API dependencies."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ocean_read.application.workspace.service import WorkspaceService
from ocean_read.domain.policy.upload_path import PathEscapeError, path_must_be_under
from ocean_read.infrastructure.persistence.validation_schema_sqlalchemy import SqlAlchemyValidationSchemaRepository
from ocean_read.infrastructure.persistence.workspace_sqlalchemy import SqlAlchemyWorkspaceRepository
from ocean_read.config import get_settings
from ocean_read.db.models import Project
from ocean_read.db.session import get_session

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def upload_root() -> Path:
    return Path(get_settings().upload_root).resolve()


def ensure_under_upload_root(candidate: Path) -> None:
    try:
        path_must_be_under(root=upload_root(), candidate=candidate)
    except PathEscapeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid upload path: {e}") from e


async def require_project(db: AsyncSession, project_id: uuid.UUID) -> Project:
    proj = (await db.execute(select(Project).where(Project.id == project_id))).scalar_one_or_none()
    if proj is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return proj


def get_workspace_service(db: SessionDep) -> WorkspaceService:
    return WorkspaceService(
        SqlAlchemyWorkspaceRepository(db),
        validation_schema_repo=SqlAlchemyValidationSchemaRepository(db),
    )


WorkspaceSvcDep = Annotated[WorkspaceService, Depends(get_workspace_service)]
