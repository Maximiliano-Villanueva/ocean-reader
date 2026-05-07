"""PostgreSQL-backed fixtures for HTTP API integration tests."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import text

_FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "wine"


def _require_postgres() -> None:
    """Skip tests when no PostgreSQL is configured or reachable."""
    try:
        from tests.sync_db import sync_engine_from_settings

        eng = sync_engine_from_settings()
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
        eng.dispose()
    except Exception as exc:  # noqa: BLE001 — broad for connectivity probes
        pytest.skip(f"PostgreSQL not reachable: {exc}")


@pytest.fixture
def validation_api_seed() -> Any:
    """Insert a project with active ``wine_schema`` 1.0 and archived ``wine_schema`` 0.9; delete after test."""

    _require_postgres()

    from tests.sync_db import sync_engine_from_settings

    org_id = "00000000-0000-4000-8000-000000000001"
    project_id = uuid.uuid4()
    schema_active_id = uuid.uuid4()
    schema_archived_id = uuid.uuid4()

    body = json.loads((_FIXTURE_DIR / "schema.json").read_text(encoding="utf-8"))
    body_json = json.dumps(body)

    eng = sync_engine_from_settings()
    try:
        with eng.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO projects (id, name, settings, organization_id)
                    VALUES (:id, :name, CAST(:settings AS jsonb), CAST(:oid AS uuid))
                    """
                ),
                {
                    "id": str(project_id),
                    "name": "validation-api-test",
                    "settings": "{}",
                    "oid": org_id,
                },
            )
            conn.execute(
                text(
                    """
                    INSERT INTO validation_schemas (id, project_id, schema_key, version_label, status, body)
                    VALUES (:id, CAST(:pid AS uuid), 'wine_schema', '1.0', 'active', CAST(:body AS jsonb))
                    """
                ),
                {"id": str(schema_active_id), "pid": str(project_id), "body": body_json},
            )
            conn.execute(
                text(
                    """
                    INSERT INTO validation_schemas (id, project_id, schema_key, version_label, status, body)
                    VALUES (:id, CAST(:pid AS uuid), 'wine_schema', '0.9', 'archived', CAST(:body AS jsonb))
                    """
                ),
                {"id": str(schema_archived_id), "pid": str(project_id), "body": body_json},
            )

        yield {
            "project_id": project_id,
            "schema_key": "wine_schema",
            "active_version": "1.0",
            "archived_version": "0.9",
        }
    finally:
        with eng.begin() as conn:
            conn.execute(text("DELETE FROM validation_schemas WHERE project_id = CAST(:pid AS uuid)"), {"pid": str(project_id)})
            conn.execute(text("DELETE FROM projects WHERE id = CAST(:pid AS uuid)"), {"pid": str(project_id)})
        eng.dispose()
