"""API tests for validation attributes and Insights cohorts."""

from __future__ import annotations

import io
import json

import httpx
import pytest

from ocean_read.main import app


def _wine_pdf_bytes() -> bytes:
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    y = 72
    for line in ("Wine QA Report", "pH: 3.5", "Alcohol: 12%", "Quality: 7"):
        page.insert_text((72, y), line)
        y += 18
    out = doc.tobytes()
    doc.close()
    return out


@pytest.mark.asyncio
async def test_validate_document_persists_attributes(validation_api_seed: dict) -> None:
    pid = validation_api_seed["project_id"]
    pdf = _wine_pdf_bytes()
    attrs = json.dumps({"batch": "March AP", "fixture": None})

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post(
            "/api/validate-document",
            data={
                "project_id": str(pid),
                "schema_id": "wine_schema",
                "schema_version": "1.0",
                "attributes": attrs,
            },
            files={"document": ("tagged.pdf", io.BytesIO(pdf), "application/pdf")},
        )
    assert r.status_code == 200, r.text
    run_id = r.json()["run_id"]

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        detail = await client.get(f"/api/projects/{pid}/validation-runs/{run_id}")
        assert detail.status_code == 200
        assert detail.json()["attributes"] == {"batch": "March AP", "fixture": None}

        vocab = await client.get(f"/api/projects/{pid}/validation-attributes")
        assert vocab.status_code == 200
        body = vocab.json()
        assert "batch" in body["keys"]
        assert "March AP" in body["values_by_key"]["batch"]


@pytest.mark.asyncio
async def test_cohort_create_and_evaluate(validation_api_seed: dict) -> None:
    pid = validation_api_seed["project_id"]
    pdf_pass = _wine_pdf_bytes()
    pdf_fail = _wine_pdf_bytes()
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    y = 72
    for line in ("Wine QA Report", "pH: 3.5", "Alcohol: 18%", "Quality: 7"):
        page.insert_text((72, y), line)
        y += 18
    pdf_fail = doc.tobytes()
    doc.close()

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        for name, data in (("pass.pdf", pdf_pass), ("fail.pdf", pdf_fail)):
            await client.post(
                "/api/validate-document",
                data={
                    "project_id": str(pid),
                    "schema_id": "wine_schema",
                    "schema_version": "1.0",
                    "attributes": json.dumps({"cohort_test": "yes"}),
                },
                files={"document": (name, io.BytesIO(data), "application/pdf")},
            )

        preview = await client.post(
            f"/api/projects/{pid}/validation-cohorts/evaluate",
            json={
                "name": "Preview",
                "filters": {
                    "attributes": [{"key": "cohort_test", "value": "yes"}],
                    "outcomes": ["PASS"],
                },
                "pass_threshold_pct": 50,
            },
        )
        assert preview.status_code == 200, preview.text
        pdata = preview.json()
        assert pdata["total"] >= 1
        assert pdata["pass_count"] >= 1
        assert all(item["outcome"] == "PASS" for item in pdata["items"])

        created = await client.post(
            f"/api/projects/{pid}/validation-cohorts",
            json={
                "name": "Tagged passes",
                "filters": {"attributes": [{"key": "cohort_test"}]},
                "pass_threshold_pct": 80,
            },
        )
        assert created.status_code == 201
        cohort_id = created.json()["id"]

        evaluated = await client.get(f"/api/projects/{pid}/validation-cohorts/{cohort_id}/evaluate")
        assert evaluated.status_code == 200
        assert evaluated.json()["total"] >= 2
