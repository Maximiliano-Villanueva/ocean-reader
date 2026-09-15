"""Internal schema DSL validation route (schema agent companion)."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from ocean_read.main import app


@pytest.mark.asyncio
async def test_internal_validate_schema_body_ok() -> None:
    body = {
        "version": "3",
        "fields": {"ph": {"type": "number"}},
        "rules": [],
        "open_ended": {
            "summary": {"extract_prompt": "Summarize", "informative_only": True}
        },
    }
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/api/internal/validate-schema-body", json={"body": body})
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["errors"] == []


@pytest.mark.asyncio
async def test_internal_validate_schema_body_repairs_extract_only_open_ended() -> None:
    body = {
        "version": "3",
        "fields": {},
        "rules": [],
        "open_ended": {"x": {"extract_prompt": "only extract"}},
    }
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/api/internal/validate-schema-body", json={"body": body})
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["normalized_body"]["open_ended"]["x"]["informative_only"] is True


@pytest.mark.asyncio
async def test_internal_validate_schema_body_rejects_evaluated_open_ended_without_prompt() -> None:
    body = {
        "version": "3",
        "fields": {},
        "rules": [],
        "open_ended": {
            "x": {"extract_prompt": "extract value", "informative_only": False},
        },
    }
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/api/internal/validate-schema-body", json={"body": body})
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is False
    assert any("evaluate_prompt" in e for e in data["errors"])
