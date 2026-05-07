"""Smoke HTTP contract — no database required."""

from fastapi.testclient import TestClient

from ocean_read.main import app


def test_health_ok() -> None:
    client = TestClient(app)
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body.get("ok") is True
