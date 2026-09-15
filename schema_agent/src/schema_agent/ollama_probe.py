"""
Probe Ollama readiness from the schema-agent service.
"""

from __future__ import annotations

import os

import httpx


def ollama_ready() -> tuple[bool, str]:
    """Return (ok, detail) after hitting Ollama ``/api/tags``."""

    base = os.environ.get("OLLAMA_BASE_URL", "http://host.docker.internal:11434").rstrip("/")
    model = os.environ.get("LLM_MODEL", "gemma4:e4b")
    try:
        r = httpx.get(f"{base}/api/tags", timeout=5.0)
        if r.status_code >= 400:
            return False, f"Ollama returned {r.status_code}"
        data = r.json()
        names = {m.get("name", "") for m in data.get("models") or [] if isinstance(m, dict)}
        # Tag may be listed as gemma4:e4b or with :latest suffix.
        if not any(model in n or n.startswith(model.split(":")[0]) for n in names):
            return (
                False,
                f"model {model!r} not found locally — run: ollama pull {model}",
            )
        return True, f"ok ({model})"
    except httpx.HTTPError as exc:
        return False, f"cannot reach Ollama at {base}: {exc}"
