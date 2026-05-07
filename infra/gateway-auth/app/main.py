"""Tiny forward-auth handler for Traefik (optional Bearer / X-Api-Token at the edge only)."""

from __future__ import annotations

import os

from fastapi import FastAPI
from starlette.requests import Request
from starlette.responses import Response

app = FastAPI()
_ENABLED = os.environ.get("EDGE_AUTH_ENABLED", "").strip().lower() in ("1", "true", "yes")
_TOKEN = os.environ.get("EDGE_API_TOKEN", "").strip()


@app.api_route("/auth", methods=["GET", "HEAD"])
def authorize(request: Request) -> Response:
    """Return 204 when the original request may proceed; otherwise 401/503."""

    if not _ENABLED:
        return Response(status_code=204)

    if not _TOKEN:
        return Response(status_code=503)

    ah = request.headers.get("authorization") or ""
    if ah.lower().startswith("bearer ") and ah[7:].strip() == _TOKEN:
        return Response(status_code=204)

    if (request.headers.get("x-api-token") or "").strip() == _TOKEN:
        return Response(status_code=204)

    return Response(status_code=401, content="Unauthorized\n", media_type="text/plain")
