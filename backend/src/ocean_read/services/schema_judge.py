"""
Schema preview judge — structured critique for the authoring agent (A2A-style feedback).

Runs after a sample-PDF preview to turn pipeline outcomes into actionable schema edits.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from ocean_read.providers.ollama import OllamaLLMClient, loads_json_maybe_with_fence

logger = logging.getLogger(__name__)


def _fallback_feedback(
    *,
    schema_body: dict[str, Any],
    validation: dict[str, Any] | None,
    dsl_errors: list[str],
) -> dict[str, Any]:
    """Deterministic critique when the judge LLM is unavailable."""

    _ = schema_body
    lines: list[str] = []
    if dsl_errors:
        lines.append(f"Fix {len(dsl_errors)} DSL error(s) before preview can run.")
    if validation:
        lines.append(f"Preview outcome: {validation.get('status')}.")
        for e in validation.get("results") or []:
            lines.append(f"Field {e.get('field')!r} failed rule {e.get('rule')!r}.")
        for a in validation.get("ambiguous_fields") or []:
            lines.append(f"Field {a.get('field')!r} is ambiguous ({a.get('candidate_count')} candidates).")
    return {
        "summary": " ".join(lines) or "No preview data yet.",
        "recommendations": lines[1:8] if len(lines) > 1 else lines,
        "priority": "high" if dsl_errors else "medium",
    }


async def analyze_preview_for_authoring(
    *,
    schema_body: dict[str, Any],
    validation: dict[str, Any] | None,
    dsl_errors: list[str],
    client: OllamaLLMClient | None = None,
) -> dict[str, Any]:
    """
    Produce structured judge feedback for the schema authoring agent.

    Returns ``summary``, ``recommendations`` (list of strings), and ``priority`` (high|medium|low).
    """

    own_client = client is None
    llm = client or OllamaLLMClient()
    try:
        payload = {
            "dsl_errors": dsl_errors,
            "validation_status": validation.get("status") if validation else None,
            "resolved_values": validation.get("resolved_values") if validation else None,
            "validation_failures": [
                {"field": e.get("field"), "rule": e.get("rule")}
                for e in (validation.get("results") or []) if validation
            ],
            "ambiguous_fields": validation.get("ambiguous_fields") if validation else None,
            "open_ended": validation.get("open_ended_results") if validation else None,
            "extraction_meta": validation.get("extraction_meta") if validation else None,
        }
        system = (
            "You are the Ocean Read schema validation judge. "
            "Given DSL errors and/or a sample PDF validation preview, produce JSON only:\n"
            '{"summary": "2-4 sentences", "recommendations": ["..."], "priority": "high|medium|low"}\n'
            "Focus on: missing aliases, loose regex, wrong types, ambiguity policy, open-ended prompts, "
            "informative_only vs validation. Be specific and actionable."
        )
        user = (
            f"SCHEMA_BODY:\n{json.dumps(schema_body, indent=2)[:14000]}\n\n"
            f"PREVIEW_RESULT:\n{json.dumps(payload, indent=2)[:14000]}\n"
        )
        raw = await llm.complete(system, user, temperature=0.1)
        data: Any = loads_json_maybe_with_fence(raw)
        if isinstance(data, dict):
            recs = data.get("recommendations")
            if not isinstance(recs, list):
                recs = []
            return {
                "summary": str(data.get("summary") or "").strip()[:2000],
                "recommendations": [str(r).strip() for r in recs if str(r).strip()][:12],
                "priority": str(data.get("priority") or "medium").strip().lower()[:20],
            }
    except Exception as exc:
        logger.info("Schema judge LLM skipped: %s", exc)
    finally:
        if own_client:
            await llm.aclose()

    return _fallback_feedback(schema_body=schema_body, validation=validation, dsl_errors=dsl_errors)
