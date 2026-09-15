"""
Shared pytest hooks — prevent live Ollama calls during contextual extraction in unit tests.

Tests that need mocked or live contextual LLM patch ``infer_document_context`` themselves
(see ``test_invoice_cursor_agent_e2e.py``).
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _disable_live_contextual_llm_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Contextual extraction is always enabled in production; tests must not hang on Ollama."""

    async def _skip_infer(*_args: object, **_kwargs: object) -> None:
        return None

    async def _noop_complete(_self: object, _system: str, _user: str, *, temperature: float = 0.0) -> str:
        return "{}"

    async def _noop_chat_json(
        _self: object, _system: str, _user: str, *, temperature: float = 0.15
    ) -> dict:
        return {}

    monkeypatch.setattr(
        "ocean_read.services.validation_contextual.infer_document_context",
        _skip_infer,
    )
    monkeypatch.setattr(
        "ocean_read.providers.ollama.OllamaLLMClient.complete",
        _noop_complete,
    )
    monkeypatch.setattr(
        "ocean_read.providers.ollama.OllamaLLMClient.chat_json",
        _noop_chat_json,
    )

    async def _noop_extraction_judge(field_map: object, *_a: object, **_k: object) -> tuple[object, tuple[()]]:
        return field_map, ()

    monkeypatch.setattr(
        "ocean_read.services.validation_pipeline.apply_extraction_judge",
        _noop_extraction_judge,
    )
