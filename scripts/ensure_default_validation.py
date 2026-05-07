#!/usr/bin/env python3
"""Ensure the stack always has usable wine-quality validation metadata after a fresh DB.

Called from ``start.sh`` after the gateway health check. Idempotent:

1. If there are **no projects**, create **Default workspace** (which seeds ``wine_quality`` @ ``1.0`` via the API).
2. For **each** existing project, if ``wine_quality`` / ``1.0`` is missing, POST the default schema version.

Uses only the public HTTP API (same as the browser) so it works with Traefik + optional edge auth.
"""

from __future__ import annotations

import json
import os
import sys
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


def project_has_wine_default(groups: list) -> bool:
    for g in groups:
        if g.get("schema_key") != SCHEMA_KEY:
            continue
        for v in g.get("versions") or []:
            if v.get("version_label") == VERSION_LABEL:
                return True
    return False


def main() -> int:
    code, raw = _request("GET", "/api/projects")
    if code != 200:
        print(f"GET /api/projects failed: HTTP {code} {raw.decode('utf-8', errors='replace')[:500]}", file=sys.stderr)
        return 1

    projects = _decode_list(raw)
    headers_note = " (with edge auth)" if _auth_headers() else ""

    if not projects:
        print(f"No projects — creating {DEFAULT_PROJECT_NAME!r}{headers_note}...")
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
            return 1
        print("Default project created; wine_quality @ 1.0 was seeded automatically.")
        return 0

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

    if missing == 0:
        print(f"All {len(projects)} project(s) already have {SCHEMA_KEY} @ {VERSION_LABEL}.")
    else:
        print(f"Updated {missing} project(s) with {SCHEMA_KEY} @ {VERSION_LABEL}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
