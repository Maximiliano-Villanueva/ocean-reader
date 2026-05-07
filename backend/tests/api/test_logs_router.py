"""Log viewer router (Compose containers)."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from ocean_read.config import get_settings
from ocean_read.main import app


@pytest.fixture(autouse=True)
def _fresh_settings_cache() -> None:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_logs_disabled_returns_404(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOG_VIEWER_ENABLED", "false")
    get_settings.cache_clear()
    client = TestClient(app)
    r = client.get("/api/logs/containers")
    assert r.status_code == 404


def test_logs_list_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOG_VIEWER_ENABLED", "true")
    monkeypatch.setenv("LOG_VIEWER_TOKEN", "")
    get_settings.cache_clear()
    fake = [
        {"id": "ab", "name": "ocean-backend-1", "service": "backend", "status": "running", "state": "running"},
    ]
    with patch("ocean_read.api.routers.logs.list_project_containers", return_value=fake):
        client = TestClient(app)
        r = client.get("/api/logs/containers")
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 1
    assert rows[0]["service"] == "backend"


def test_logs_token_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOG_VIEWER_ENABLED", "true")
    monkeypatch.setenv("LOG_VIEWER_TOKEN", "secret")
    get_settings.cache_clear()
    client = TestClient(app)
    assert client.get("/api/logs/containers").status_code == 401
    with patch("ocean_read.api.routers.logs.list_project_containers", return_value=[]):
        r2 = client.get("/api/logs/containers", headers={"X-Log-Viewer-Token": "secret"})
    assert r2.status_code == 200


def test_logs_tail_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOG_VIEWER_ENABLED", "true")
    monkeypatch.setenv("LOG_VIEWER_TOKEN", "")
    get_settings.cache_clear()
    with patch("ocean_read.api.routers.logs.tail_container_logs", return_value="line1\nline2"):
        client = TestClient(app)
        r = client.get("/api/logs/containers/backendid/tail?tail=10")
    assert r.status_code == 200
    assert "line1" in r.json()["text"]
