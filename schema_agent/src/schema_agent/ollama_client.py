"""
Direct Ollama ``/api/chat`` client (no LiteLLM / ADK — avoids unsupported ``tool_responses`` roles).
"""

from __future__ import annotations

import os
from typing import Any

import httpx


async def ollama_chat(
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.2,
) -> str:
    """Single non-streaming chat completion; returns assistant message text."""

    base = os.environ.get("OLLAMA_BASE_URL", "http://host.docker.internal:11434").rstrip("/")
    model = os.environ.get("LLM_MODEL", "gemma4:e4b")
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {"temperature": temperature},
    }
    async with httpx.AsyncClient(base_url=base, timeout=600.0) as client:
        r = await client.post("/api/chat", json=payload)
        if r.status_code >= 400:
            try:
                err = r.json().get("error", r.text)
            except Exception:
                err = r.text
            raise RuntimeError(f"Ollama chat failed ({r.status_code}): {err}")
        data = r.json()
    msg = data.get("message") or {}
    content = msg.get("content")
    return "" if content is None else str(content)
