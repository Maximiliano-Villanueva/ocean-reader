"""Workspace application service unit tests — repository port is mocked."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest

from ocean_read.application.ports.workspace import WorkspaceRepository
from ocean_read.application.workspace.service import WorkspaceService
from ocean_read.domain.exceptions import ProjectNotFound
from ocean_read.domain.tenancy import DEFAULT_ORGANIZATION_ID


@pytest.mark.asyncio
async def test_create_project_assigns_default_org() -> None:
    repo = AsyncMock(spec=WorkspaceRepository)
    svc = WorkspaceService(repo)
    await svc.create_project("Acme Corp")
    p = repo.add_project.await_args.args[0]
    assert p.organization_id == DEFAULT_ORGANIZATION_ID


@pytest.mark.asyncio
async def test_create_project_without_validation_repo_skips_seed() -> None:
    repo = AsyncMock(spec=WorkspaceRepository)
    svc = WorkspaceService(repo)
    await svc.create_project("No Seed Co")
    repo.add_project.assert_awaited_once()
    repo.commit_refresh.assert_awaited_once()
    assert repo.commit_refresh.await_args.args[0].name == "No Seed Co"


@pytest.mark.asyncio
async def test_create_project_with_validation_repo_seeds_wine_quality() -> None:
    repo = AsyncMock(spec=WorkspaceRepository)
    vs = AsyncMock()
    svc = WorkspaceService(repo, validation_schema_repo=vs)
    await svc.create_project("Vineyard LLC")
    vs.create_version.assert_awaited_once()
    seeded_project = repo.add_project.await_args.args[0]
    kw = vs.create_version.await_args.kwargs
    assert kw["project_id"] == seeded_project.id
    assert kw["schema_key"] == "wine_quality"
    assert kw["version_label"] == "1.0"
    assert "fields" in kw["body"]
    repo.commit_refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_project_missing_raises() -> None:
    repo = AsyncMock(spec=WorkspaceRepository)
    repo.get_project.return_value = None
    svc = WorkspaceService(repo)
    with pytest.raises(ProjectNotFound):
        await svc.delete_project(uuid.uuid4())
