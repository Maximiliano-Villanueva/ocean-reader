"""LLM-assisted authoring for M3 ``cross_field_rules`` expressions (optional, gated by settings).

The model proposes JSON; this module validates identifiers against an allow-list and
smoke-checks evaluation with dummy numeric bindings so only sandbox-safe expressions surface.
"""

from __future__ import annotations

import logging
from typing import Any

from ocean_read.domain.validation.expression_evaluator import (
    ExpressionEvaluationError,
    evaluate_boolean_expression,
    expression_identifiers,
)
from ocean_read.providers.ollama import OllamaLLMClient, loads_json_maybe_with_fence

logger = logging.getLogger(__name__)

_SYSTEM = (
    "You output JSON only for a wine/lab schema cross-field rule. "
    "Keys: expression (string, boolean formula), error_message (string, may use {field} placeholders), "
    "id (string, snake_case, optional). "
    "expression may use ONLY these identifiers as variables: the allowed field list provided by the user. "
    "Operators: numbers, + - * /, comparisons > >= < <= == !=, AND OR NOT, parentheses. "
    "No function calls, no strings, no extra identifiers."
)


def validate_llm_cross_field_payload(
    data: Any,
    allowed_field_names: frozenset[str],
) -> dict[str, str]:
    """Validate parsed JSON from the model; returns ``id``, ``expression``, ``error_message``."""

    if not isinstance(data, dict):
        raise ValueError("Model output must be a JSON object")
    expr = str(data.get("expression") or "").strip()
    if not expr:
        raise ValueError("Missing expression")
    msg = str(data.get("error_message") or "").strip()
    if not msg:
        raise ValueError("Missing error_message")
    rid = str(data.get("id") or "cross_field_rule").strip() or "cross_field_rule"
    try:
        names = expression_identifiers(expr)
    except ExpressionEvaluationError as exc:
        raise ValueError(f"Invalid expression: {exc}") from exc
    if not names:
        raise ValueError("Expression must reference at least one allowed field")
    unknown = [n for n in names if n not in allowed_field_names]
    if unknown:
        raise ValueError(f"Expression uses unknown identifiers: {unknown}")
    binding = {n: 1.0 for n in names}
    try:
        evaluate_boolean_expression(expr, binding)
    except ExpressionEvaluationError as exc:
        raise ValueError(f"Expression does not evaluate as boolean with numeric bindings: {exc}") from exc
    return {"id": rid, "expression": expr, "error_message": msg}


async def suggest_cross_field_rule_from_nl(
    *,
    natural_language: str,
    allowed_field_names: list[str],
    client: OllamaLLMClient,
) -> dict[str, str]:
    """Call Ollama with temperature 0 and return a validated rule dict."""

    text = (natural_language or "").strip()
    if not text:
        raise ValueError("natural_language must be non-empty")
    allowed = frozenset(str(x).strip() for x in allowed_field_names if str(x).strip())
    if not allowed:
        raise ValueError("allowed_field_names must be non-empty")
    fields_csv = ", ".join(sorted(allowed))
    user = (
        f"Allowed field names (use only these as bare identifiers): {fields_csv}\n\n"
        f"Author intent (plain language):\n{text}\n"
    )
    raw = await client.complete(_SYSTEM, user, temperature=0.0)
    try:
        payload = loads_json_maybe_with_fence(raw)
    except ValueError as exc:
        logger.info("Cross-field assist: bad JSON from model: %s", exc)
        raise ValueError("Model did not return valid JSON") from exc
    return validate_llm_cross_field_payload(payload, allowed)
