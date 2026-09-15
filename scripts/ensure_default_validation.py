#!/usr/bin/env python3
"""Ensure the stack always has usable wine-quality validation metadata after a fresh DB.

Called from ``start.sh`` after the gateway health check. Idempotent:

1. Wait until ``GET /api/projects`` succeeds (Traefik + migrations + optional edge auth).
2. Create **Default workspace** when no project has that exact name (seeds ``wine_quality`` @ ``1.0`` via the API).
3. For **each** project, if ``wine_quality`` / ``1.0`` is missing, POST the default schema version.

Uses only the public HTTP API (same as the browser) so it works with Traefik + optional edge auth.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request

DEFAULT_PROJECT_NAME = "Default workspace"
SCHEMA_KEY = "wine_quality"
VERSION_LABEL = "1.0"


def _base_url() -> str:
    port = os.environ.get("GATEWAY_HTTP_PORT", "8080").strip() or "8080"
    return f"http://127.0.0.1:{port}"


def _auth_headers() -> dict[str, str]:
    enabled = os.environ.get("EDGE_AUTH_ENABLED", "false").strip().lower()
    if enabled in {"1", "true", "yes"}:
        token = (os.environ.get("EDGE_API_TOKEN") or "").strip()
        if not token:
            print("Error: EDGE_AUTH_ENABLED is set but EDGE_API_TOKEN is empty.", file=sys.stderr)
            sys.exit(2)
        return {"Authorization": f"Bearer {token}"}
    return {}


def _request(
    method: str,
    path: str,
    *,
    body: dict | None = None,
) -> tuple[int, bytes]:
    url = _base_url() + path
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {
        **_auth_headers(),
        "Accept": "application/json",
    }
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.getcode(), resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def _decode_list(raw: bytes) -> list:
    if not raw.strip():
        return []
    return json.loads(raw.decode("utf-8"))


def find_project_by_name(projects: list, name: str) -> dict | None:
    """Return the first project dict whose ``name`` matches exactly."""

    for p in projects:
        if p.get("name") == name:
            return p
    return None


def project_has_wine_default(groups: list) -> bool:
    for g in groups:
        if g.get("schema_key") != SCHEMA_KEY:
            continue
        for v in g.get("versions") or []:
            if v.get("version_label") == VERSION_LABEL:
                return True
    return False


def wait_until_projects_api_ready(
    *,
    max_seconds: int | None = None,
    interval_seconds: float | None = None,
) -> tuple[int, bytes] | None:
    """Poll ``GET /api/projects`` until HTTP 200 or timeout. Returns last response on success."""

    max_s = max_seconds if max_seconds is not None else int(os.environ.get("SEED_MAX_WAIT_SECONDS", "90"))
    interval = interval_seconds if interval_seconds is not None else float(
        os.environ.get("SEED_WAIT_INTERVAL_SECONDS", "3")
    )
    deadline = time.monotonic() + max_s
    last_code = 0
    last_raw = b""
    while time.monotonic() < deadline:
        last_code, last_raw = _request("GET", "/api/projects")
        if last_code == 200:
            return last_code, last_raw
        time.sleep(interval)
    print(
        f"GET /api/projects did not return 200 within {max_s}s (last HTTP {last_code} "
        f"{last_raw.decode('utf-8', errors='replace')[:300]})",
        file=sys.stderr,
    )
    return None


def ensure_default_workspace_project(*, headers_note: str) -> tuple[list, int]:
    """Create **Default workspace** when missing; return updated project list and exit code."""

    code, raw = _request("GET", "/api/projects")
    if code != 200:
        print(f"GET /api/projects failed: HTTP {code} {raw.decode('utf-8', errors='replace')[:500]}", file=sys.stderr)
        return [], 1

    projects = _decode_list(raw)
    if find_project_by_name(projects, DEFAULT_PROJECT_NAME) is not None:
        return projects, 0

    print(f"Creating {DEFAULT_PROJECT_NAME!r}{headers_note}...")
    code2, raw2 = _request(
        "POST",
        "/api/projects",
        body={"name": DEFAULT_PROJECT_NAME},
    )
    if code2 not in {200, 201}:
        print(
            f"POST /api/projects failed: HTTP {code2} {raw2.decode('utf-8', errors='replace')[:500]}",
            file=sys.stderr,
        )
        return projects, 1

    print("Default workspace created; wine_quality @ 1.0 was seeded automatically.")
    code3, raw3 = _request("GET", "/api/projects")
    if code3 != 200:
        print(f"GET /api/projects failed after create: HTTP {code3}", file=sys.stderr)
        return projects, 1
    return _decode_list(raw3), 0


def ensure_wine_schema_on_all_projects(projects: list, *, headers_note: str) -> int:
    """POST default wine schema on projects that lack ``wine_quality`` @ ``1.0``."""

    missing = 0
    for p in projects:
        pid = p.get("id")
        if not pid:
            continue
        path = f"/api/projects/{pid}/validation-schemas"
        c3, r3 = _request("GET", path)
        if c3 != 200:
            print(f"GET {path} failed: HTTP {c3}", file=sys.stderr)
            return 1
        groups = _decode_list(r3)
        if project_has_wine_default(groups):
            continue
        missing += 1
        print(f"Project {pid}: adding {SCHEMA_KEY} @ {VERSION_LABEL}{headers_note}...")
        c4, r4 = _request(
            "POST",
            path,
            body={"schema_key": SCHEMA_KEY, "version_label": VERSION_LABEL},
        )
        if c4 != 201:
            print(
                f"POST {path} failed: HTTP {c4} {r4.decode('utf-8', errors='replace')[:500]}",
                file=sys.stderr,
            )
            return 1

    if not projects:
        print("No projects to update.", file=sys.stderr)
        return 1
    if missing == 0:
        print(f"All {len(projects)} project(s) already have {SCHEMA_KEY} @ {VERSION_LABEL}.")
    else:
        print(f"Updated {missing} project(s) with {SCHEMA_KEY} @ {VERSION_LABEL}.")
    return 0


def has_default_workspace_project() -> bool:
    """Return True when **Default workspace** is listed (used by ``start.sh`` verification)."""

    code, raw = _request("GET", "/api/projects")
    if code != 200:
        return False
    return find_project_by_name(_decode_list(raw), DEFAULT_PROJECT_NAME) is not None


def main() -> int:
    ready = wait_until_projects_api_ready()
    if ready is None:
        return 1

    headers_note = " (with edge auth)" if _auth_headers() else ""

    projects, rc = ensure_default_workspace_project(headers_note=headers_note)
    if rc != 0:
        return rc

    return ensure_wine_schema_on_all_projects(projects, headers_note=headers_note)


if __name__ == "__main__":
    raise SystemExit(main())
