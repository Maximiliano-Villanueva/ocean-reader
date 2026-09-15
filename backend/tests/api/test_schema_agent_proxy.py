"""Schema agent chat proxy (mocked downstream service)."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from ocean_read.main import app


@pytest.mark.asyncio
async def test_schema_agent_chat_proxy(monkeypatch: pytest.MonkeyPatch) -> None:
    project_id = uuid.uuid4()

    async def _fake_require(db, pid):  # noqa: ANN001
        return None

    monkeypatch.setattr("ocean_read.api.routers.validation.require_project", _fake_require)

    mock_resp = type(
        "R",
        (),
        {
            "status_code": 200,
            "text": "",
            "raise_for_status": lambda self: None,
            "json": lambda self: {
                "reply": "Added field.",
                "schema_body": {"version": "3", "fields": {}, "rules": []},
            },
        },
    )()

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("ocean_read.api.routers.validation.httpx.AsyncClient", return_value=mock_client):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.post(
                f"/api/projects/{project_id}/schema-agent/chat",
                json={
                    "messages": [{"role": "user", "content": "Add quality field"}],
                    "schema_body": {"fields": {}, "rules": []},
                },
            )
    assert r.status_code == 200
    data = r.json()
    assert "reply" in data
    assert data["schema_body"]["version"] == "3"
