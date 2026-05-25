"""HTTP contract tests for validation routes (multipart PDF upload + schema lifecycle).

Requires PostgreSQL with migrations applied (``DATABASE_URL`` / default Compose DB).
"""

from __future__ import annotations

import io
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from ocean_read.main import app


def _wine_pdf_bytes(*, alcohol_line: str = "Alcohol: 12%", include_quality: bool = True) -> bytes:
    """Minimal Wine QA PDF compatible with regex extractors."""

    import fitz

    doc = fitz.open()
    page = doc.new_page()
    y = 72
    lines = ["Wine QA Report", "pH: 3.5", alcohol_line]
    if include_quality:
        lines.append("Quality: 7")
    for line in lines:
        page.insert_text((72, y), line)
        y += 18
    out = doc.tobytes()
    doc.close()
    return out


@pytest.mark.asyncio
async def test_validate_document_pass(validation_api_seed: dict) -> None:
    pid = validation_api_seed["project_id"]
    pdf = _wine_pdf_bytes(alcohol_line="Alcohol: 12%")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post(
            "/api/validate-document",
            data={
                "project_id": str(pid),
                "schema_id": "wine_schema",
                "schema_version": "1.0",
            },
            files={"document": ("lab.pdf", io.BytesIO(pdf), "application/pdf")},
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "PASS"
    assert body["schema_id"] == "wine_schema"
    assert body["schema_version"] == "1.0"
    assert body["results"] == []
    outcomes = body.get("field_rule_outcomes") or []
    with_bbox = [
        o
        for o in outcomes
        if o.get("evidence") and isinstance(o["evidence"].get("bbox"), list) and len(o["evidence"]["bbox"]) >= 4
    ]
    assert with_bbox, "PASS runs should include bbox on field evidence for PDF highlighting"


@pytest.mark.asyncio
async def test_validate_document_fail_out_of_range_with_evidence(validation_api_seed: dict) -> None:
    pid = validation_api_seed["project_id"]
    pdf = _wine_pdf_bytes(alcohol_line="Alcohol: 18%")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post(
            "/api/validate-document",
            data={
                "project_id": str(pid),
                "schema_id": "wine_schema",
                "schema_version": "1.0",
            },
            files={"document": ("lab.pdf", io.BytesIO(pdf), "application/pdf")},
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "FAIL"
    alc = next(x for x in body["results"] if x["field"] == "alcohol")
    assert alc["rule"] == "range_validation"
    assert alc["evidence"] is not None
    assert alc["evidence"]["page"] == 1
    assert "Alcohol" in (alc["evidence"].get("text") or "")


@pytest.mark.asyncio
async def test_validate_document_rejects_non_pdf(validation_api_seed: dict) -> None:
    pid = validation_api_seed["project_id"]
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post(
            "/api/validate-document",
            data={
                "project_id": str(pid),
                "schema_id": "wine_schema",
                "schema_version": "1.0",
            },
            files={"document": ("note.txt", io.BytesIO(b"not a pdf"), "text/plain")},
        )
    assert r.status_code == 400
    assert "pdf" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_validate_document_unknown_schema_version_returns_404(validation_api_seed: dict) -> None:
    pid = validation_api_seed["project_id"]
    pdf = _wine_pdf_bytes()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post(
            "/api/validate-document",
            data={
                "project_id": str(pid),
                "schema_id": "wine_schema",
                "schema_version": "99.0",
            },
            files={"document": ("lab.pdf", io.BytesIO(pdf), "application/pdf")},
        )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_validate_document_archived_schema_returns_409(validation_api_seed: dict) -> None:
    pid = validation_api_seed["project_id"]
    pdf = _wine_pdf_bytes()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post(
            "/api/validate-document",
            data={
                "project_id": str(pid),
                "schema_id": "wine_schema",
                "schema_version": validation_api_seed["archived_version"],
            },
            files={"document": ("lab.pdf", io.BytesIO(pdf), "application/pdf")},
        )
    assert r.status_code == 409
    assert "active" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_validate_document_pdf_exceeds_limit_returns_413(
    validation_api_seed: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import ocean_read.api.routers.validation as vr

    monkeypatch.setattr(vr, "_MAX_VALIDATE_BYTES", 100)
    pid = validation_api_seed["project_id"]
    pdf = b"%PDF-1.4" + b"x" * 200
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post(
            "/api/validate-document",
            data={
                "project_id": str(pid),
                "schema_id": "wine_schema",
                "schema_version": "1.0",
            },
            files={"document": ("big.pdf", io.BytesIO(pdf), "application/pdf")},
        )
    assert r.status_code == 413


@pytest.mark.asyncio
async def test_tc_api_007_missing_required_form_field_returns_422() -> None:
    """TC-API-007: FastAPI returns 422 when required multipart fields are absent."""

    pdf = _wine_pdf_bytes()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post(
            "/api/validate-document",
            data={
                "schema_id": "wine_schema",
                "schema_version": "1.0",
            },
            files={"document": ("lab.pdf", io.BytesIO(pdf), "application/pdf")},
        )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_list_validation_schemas(validation_api_seed: dict) -> None:
    pid = validation_api_seed["project_id"]
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get(f"/api/projects/{pid}/validation-schemas")
    assert r.status_code == 200
    groups = r.json()
    assert len(groups) == 1
    assert groups[0]["schema_key"] == "wine_schema"
    labels = {v["version_label"] for v in groups[0]["versions"]}
    assert labels == {"1.0", "0.9"}


@pytest.mark.asyncio
async def test_post_validation_schema_version_and_duplicate_409(validation_api_seed: dict) -> None:
    pid = validation_api_seed["project_id"]
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post(
            f"/api/projects/{pid}/validation-schemas",
            json={"schema_key": "extra_wine", "version_label": "0.1"},
        )
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["version_label"] == "0.1"
        assert data["status"] == "active"
        r2 = await client.post(
            f"/api/projects/{pid}/validation-schemas",
            json={"schema_key": "extra_wine", "version_label": "0.1"},
        )
        assert r2.status_code == 409


@pytest.mark.asyncio
async def test_post_validation_schema_rejects_invalid_m3_cross_field(validation_api_seed: dict) -> None:
    """M3: invalid ``cross_field_rules`` expression returns 400 before DB insert."""

    pid = validation_api_seed["project_id"]
    bad_body = {
        "version": "2",
        "fields": {"a": {"type": "number"}},
        "rules": [],
        "cross_field_rules": [{"id": "x", "expression": "(", "error_message": "m", "fields": ["a"]}],
    }
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post(
            f"/api/projects/{pid}/validation-schemas",
            json={"schema_key": "m3_bad", "version_label": "0.1", "body": bad_body},
        )
    assert r.status_code == 400
    detail = r.json().get("detail")
    assert isinstance(detail, dict)
    assert "schema_dsl_errors" in detail


@pytest.mark.asyncio
async def test_suggest_cross_field_rule_forbidden_when_disabled(
    validation_api_seed: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("VALIDATION_SCHEMA_LLM_ASSIST_ENABLED", raising=False)
    from ocean_read.config import get_settings

    get_settings.cache_clear()
    pid = validation_api_seed["project_id"]
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post(
            f"/api/projects/{pid}/validation-schemas/suggest-cross-field-rule",
            json={"natural_language": "test", "allowed_field_names": ["a"]},
        )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_suggest_cross_field_rule_ok_when_enabled(
    validation_api_seed: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VALIDATION_SCHEMA_LLM_ASSIST_ENABLED", "true")
    from ocean_read.config import get_settings

    get_settings.cache_clear()
    pid = validation_api_seed["project_id"]
    with patch(
        "ocean_read.api.routers.validation.suggest_cross_field_rule_from_nl",
        new_callable=AsyncMock,
    ) as m:
        m.return_value = {
            "id": "high_alcohol_quality",
            "expression": "quality >= 5 OR alcohol < 12",
            "error_message": "Quality must track alcohol",
        }
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post(
                f"/api/projects/{pid}/validation-schemas/suggest-cross-field-rule",
                json={
                    "natural_language": "If alcohol is at least 12, quality must be at least 5",
                    "allowed_field_names": ["alcohol", "quality"],
                },
            )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["expression"] == "quality >= 5 OR alcohol < 12"
    assert data["id"] == "high_alcohol_quality"


@pytest.mark.asyncio
async def test_post_project_seeds_wine_quality_schema(validation_api_seed: dict) -> None:
    """POST /api/projects creates default wine_quality @ 1.0 for validation."""

    _ = validation_api_seed
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/api/projects", json={"name": "pytest-wine-seed-default-schema"})
        assert r.status_code == 200, r.text
        pid = r.json()["id"]
        r2 = await client.get(f"/api/projects/{pid}/validation-schemas")
        assert r2.status_code == 200, r2.text
        groups = r2.json()
        keys = {g["schema_key"] for g in groups}
        assert "wine_quality" in keys
        wq = next(g for g in groups if g["schema_key"] == "wine_quality")
        assert any(v["version_label"] == "1.0" and v["status"] == "active" for v in wq["versions"])
        rd = await client.delete(f"/api/projects/{pid}")
        assert rd.status_code == 200
