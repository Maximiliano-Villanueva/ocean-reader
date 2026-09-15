"""M2: persisted pdf_hash, snapshots, list filters, sub-resources (requires PostgreSQL + migrations)."""

from __future__ import annotations

import io

import httpx
import pytest

from ocean_read.domain.validation.pdf_hash import compute_pdf_hash
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
async def test_tc_m2_validation_run_stores_hash_and_snapshots(validation_api_seed: dict) -> None:
    """POST validate persists pdf_hash and snapshot-backed sub-resources."""

    pid = validation_api_seed["project_id"]
    pdf = _wine_pdf_bytes()
    expected_hash = compute_pdf_hash(pdf)

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
    run_id = body["run_id"]
    assert run_id

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        detail = await client.get(f"/api/projects/{pid}/validation-runs/{run_id}")
        assert detail.status_code == 200
        djson = detail.json()
        assert djson["pdf_hash"] == expected_hash

        blocks = await client.get(f"/api/projects/{pid}/validation-runs/{run_id}/blocks")
        assert blocks.status_code == 200
        assert isinstance(blocks.json(), list)
        assert len(blocks.json()) >= 1

        cands = await client.get(f"/api/projects/{pid}/validation-runs/{run_id}/candidates")
        assert cands.status_code == 200
        assert len(cands.json()) >= 1

        resolved = await client.get(f"/api/projects/{pid}/validation-runs/{run_id}/resolved")
        assert resolved.status_code == 200
        rj = resolved.json()
        assert "ph" in rj and "alcohol" in rj


@pytest.mark.asyncio
async def test_tc_m2_list_runs_filtered_by_status(validation_api_seed: dict) -> None:
    """List endpoint honors status query param (maps to outcome column)."""

    pid = validation_api_seed["project_id"]
    pdf_pass = _wine_pdf_bytes(alcohol_line="Alcohol: 12%")
    pdf_fail = _wine_pdf_bytes(alcohol_line="Alcohol: 18%")

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            "/api/validate-document",
            data={
                "project_id": str(pid),
                "schema_id": "wine_schema",
                "schema_version": "1.0",
            },
            files={"document": ("p.pdf", io.BytesIO(pdf_pass), "application/pdf")},
        )
        await client.post(
            "/api/validate-document",
            data={
                "project_id": str(pid),
                "schema_id": "wine_schema",
                "schema_version": "1.0",
            },
            files={"document": ("f.pdf", io.BytesIO(pdf_fail), "application/pdf")},
        )

        r_all = await client.get(f"/api/projects/{pid}/validation-runs?page=1&page_size=25")
        assert r_all.status_code == 200
        total_all = r_all.json()["total"]
        assert total_all >= 2

        r_pass = await client.get(f"/api/projects/{pid}/validation-runs?status=PASS")
        assert r_pass.status_code == 200
        pj = r_pass.json()
        assert pj["total"] >= 1
        assert all(i["outcome"] == "PASS" for i in pj["items"])


@pytest.mark.asyncio
async def test_m2_archived_run_hidden_from_default_list_included_with_flag(validation_api_seed: dict) -> None:
    """Archived runs are omitted from the default list and visible when ``include_hidden=true``."""

    pid = validation_api_seed["project_id"]
    pdf = _wine_pdf_bytes()

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post(
            "/api/validate-document",
            data={
                "project_id": str(pid),
                "schema_id": "wine_schema",
                "schema_version": "1.0",
            },
            files={"document": ("a.pdf", io.BytesIO(pdf), "application/pdf")},
        )
        assert r.status_code == 200, r.text
        run_id = r.json()["run_id"]

        arch = await client.patch(
            f"/api/projects/{pid}/validation-runs/{run_id}",
            json={"archived": True},
        )
        assert arch.status_code == 200, arch.text

        default_list = await client.get(f"/api/projects/{pid}/validation-runs?page=1&page_size=25")
        assert default_list.status_code == 200
        ids_default = {x["id"] for x in default_list.json()["items"]}
        assert run_id not in ids_default

        hidden_list = await client.get(
            f"/api/projects/{pid}/validation-runs?page=1&page_size=25&include_hidden=true",
        )
        assert hidden_list.status_code == 200
        hj = hidden_list.json()
        ids_hidden = {x["id"] for x in hj["items"]}
        assert run_id in ids_hidden
        row = next(x for x in hj["items"] if x["id"] == run_id)
        assert row.get("archived_at")
        assert row.get("deleted_at") in (None, "")

        detail = await client.get(f"/api/projects/{pid}/validation-runs/{run_id}")
        assert detail.status_code == 200


@pytest.mark.asyncio
async def test_m2_soft_deleted_run_and_restore(validation_api_seed: dict) -> None:
    """DELETE marks a run as soft-deleted; PATCH restore clears lifecycle flags."""

    pid = validation_api_seed["project_id"]
    pdf = _wine_pdf_bytes()

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post(
            "/api/validate-document",
            data={
                "project_id": str(pid),
                "schema_id": "wine_schema",
                "schema_version": "1.0",
            },
            files={"document": ("d.pdf", io.BytesIO(pdf), "application/pdf")},
        )
        assert r.status_code == 200, r.text
        run_id = r.json()["run_id"]

        del_r = await client.delete(f"/api/projects/{pid}/validation-runs/{run_id}")
        assert del_r.status_code == 200, del_r.text

        default_list = await client.get(f"/api/projects/{pid}/validation-runs?page=1&page_size=25")
        assert run_id not in {x["id"] for x in default_list.json()["items"]}

        hidden = await client.get(f"/api/projects/{pid}/validation-runs?include_hidden=true")
        assert run_id in {x["id"] for x in hidden.json()["items"]}
        row = next(x for x in hidden.json()["items"] if x["id"] == run_id)
        assert row.get("deleted_at")

        rest = await client.patch(
            f"/api/projects/{pid}/validation-runs/{run_id}",
            json={"restore": True},
        )
        assert rest.status_code == 200, rest.text

        again = await client.get(f"/api/projects/{pid}/validation-runs?page=1&page_size=25")
        assert run_id in {x["id"] for x in again.json()["items"]}


@pytest.mark.asyncio
async def test_m2_list_runs_filter_by_version_and_document_substring(validation_api_seed: dict) -> None:
    """List endpoint supports ``version_label`` and case-insensitive ``document_contains``."""

    pid = validation_api_seed["project_id"]
    pdf = _wine_pdf_bytes()

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            "/api/validate-document",
            data={
                "project_id": str(pid),
                "schema_id": "wine_schema",
                "schema_version": "1.0",
            },
            files={"document": ("alpha_report_q1.pdf", io.BytesIO(pdf), "application/pdf")},
        )
        await client.post(
            "/api/validate-document",
            data={
                "project_id": str(pid),
                "schema_id": "wine_schema",
                "schema_version": "1.0",
            },
            files={"document": ("beta_summary.pdf", io.BytesIO(pdf), "application/pdf")},
        )

        by_name = await client.get(
            f"/api/projects/{pid}/validation-runs?document_contains=alpha_report",
        )
        assert by_name.status_code == 200
        names = {i["document_filename"] for i in by_name.json()["items"]}
        assert names == {"alpha_report_q1.pdf"}

        by_ver = await client.get(
            f"/api/projects/{pid}/validation-runs?schema_key=wine_schema&version_label=1.0",
        )
        assert by_ver.status_code == 200
        assert by_ver.json()["total"] >= 2
        assert all(
            i["version_label"] == "1.0" and i["schema_key"] == "wine_schema" for i in by_ver.json()["items"]
        )


@pytest.mark.asyncio
async def test_manual_correction_creates_run_revision_and_revalidates(validation_api_seed: dict) -> None:
    """POST revisions saves corrected values and updates outcome."""

    pid = validation_api_seed["project_id"]
    pdf = _wine_pdf_bytes(alcohol_line="Alcohol: 18%")

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post(
            "/api/validate-document",
            data={
                "project_id": str(pid),
                "schema_id": "wine_schema",
                "schema_version": "1.0",
            },
            files={"document": ("fail_alcohol.pdf", io.BytesIO(pdf), "application/pdf")},
        )
        assert created.status_code == 200, created.text
        parent_id = created.json()["run_id"]
        assert created.json()["status"] == "FAIL"

        revised = await client.post(
            f"/api/projects/{pid}/validation-runs/{parent_id}/revisions",
            json={"corrections": {"alcohol": 9.4}, "note": "Lab confirmed 9.4%"},
        )
        assert revised.status_code == 201, revised.text
        body = revised.json()
        assert body["parent_run_id"] == parent_id
        assert body["revision_number"] == 2
        assert body["outcome"] == "PASS"
        assert body["report"]["resolved_values"]["alcohol"] == 9.4
        assert body["report"]["manual_corrections"]["alcohol"]["to"] == 9.4

        parent = await client.get(f"/api/projects/{pid}/validation-runs/{parent_id}")
        assert parent.status_code == 200
        assert parent.json()["outcome"] == "FAIL"
