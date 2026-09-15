"""
Schema authoring via Ollama (``gemma4:e4b``). Normalizes and validates DSL until publishable.
"""

from __future__ import annotations

import copy
import json
import re
from typing import Any

from schema_agent.ollama_client import ollama_chat
from schema_agent.schema_normalize import normalize_schema_body
from schema_agent.tools import get_engine_capabilities, validate_schema_body

_MAX_REPAIR_TURNS = 4

_INSTRUCTION = """You are the Ocean Read schema authoring assistant.

Turn the user's request into a **DSL version 3** validation schema JSON body.

## Strict vs open-ended

| User says | Put in schema |
|-----------|----------------|
| "extract X **without validation**" / "informative only" | ``open_ended`` with ``informative_only: true`` |
| "extract and **validate**" / "must be" / "equals" | ``fields`` (strict) with type, ``required``, ``aliases``, ``regex_hint`` |
| Dates like "fecha de emisión" | ``fields`` type ``date`` + Spanish aliases |
| Total / amount with a fixed value (e.g. 20 USD) | ``fields`` type ``number`` with ``min`` and ``max`` both 20 |

## Rules

- **Never** put open-ended specs inside ``fields`` with ``type: open_ended``. Use top-level ``open_ended`` only.
- **Never** use per-field ``rules`` arrays. Use ``min``/``max`` on numbers or top-level ``cross_field_rules``.
- Every **strict** field needs ``aliases`` (PDF label phrases) and usually a **label-anchored** ``regex_hint`` (never bare ``[A-Z0-9]+``), except LLM-primary fields below.
- **Canonical field keys** in ``fields`` (never invent synonyms):
  - ``issue_date`` for fecha de emisión
  - ``due_date`` for fecha de vencimiento
  - ``total_due`` for total / importe por pagar (use ``semantic_role``: ``document_total`` — never name a field ``document_total``)
  - ``invoice_number``, ``recipient_email``
- Set ``semantic_role`` when layout matters (``recipient``, ``issuer``, ``document_total``, ``line_item``, etc.).
- Optional ``extraction_hint`` for contextual LLM (one sentence: what to look for and what to ignore).
- Top-level ``extraction``: ``{{"understand_document": true, "context_pass": "when_needed"}}`` (default).
- Multiple PDF hits: ``on_ambiguity`` ``first`` | ``last`` | ``best_match`` | ``highest_confidence``.
- Dates in prose: ``type: "date"`` + aliases; ``llm_fallback: true`` if regex may miss.
- Open-ended entries **must** use ``extract_prompt`` (not ``description`` or ``prompt`` alone).
- Extraction-only / "without validation" → ``informative_only: true`` + ``extract_prompt`` (no ``evaluate_prompt``).
- If open-ended affects PASS/FAIL → ``evaluate_prompt`` + ``evaluation_tags``: ["pass", "fail", "ambiguous"].
- Invoice number via LLM (not regex) → ``fields.invoice_number`` with ``llm_fallback: true``, ``llm_only: true``,
  ``extraction_hint`` describing what to extract, and **omit** ``regex_hint`` entirely.

The user may edit JSON between turns. ``CURRENT_SCHEMA_JSON`` is the draft to merge.

Reply conversationally, then the **full** body in:

```schema
{ ... }
```
"""


def _apply_transcript_policies(messages: list[dict[str, str]], body: dict[str, Any]) -> dict[str, Any]:
    """Apply explicit user extraction policies that the LLM may omit from the schema JSON."""

    transcript = " ".join(str(m.get("content") or "") for m in messages).lower()
    out = copy.deepcopy(body)
    fields = out.get("fields")
    if not isinstance(fields, dict):
        return out

    if re.search(r"invoice\s*number.*llm|llm.*invoice\s*number|llm\s+not\s+regex", transcript):
        inv = fields.setdefault(
            "invoice_number",
            {"type": "string", "required": True, "aliases": ["número de factura", "invoice number"]},
        )
        if isinstance(inv, dict):
            inv["llm_fallback"] = True
            inv["llm_only"] = True
            inv.pop("regex_hint", None)
            if not str(inv.get("extraction_hint") or "").strip():
                inv["extraction_hint"] = (
                    "Extract the unique invoice identifier using document context; "
                    "do not rely on a bare alphanumeric pattern."
                )

    return out


def _extract_schema_from_text(text: str, fallback: dict[str, Any]) -> dict[str, Any]:
    if "```schema" in text:
        chunk = text.split("```schema", 1)[1].split("```", 1)[0]
        try:
            return json.loads(chunk.strip())
        except json.JSONDecodeError:
            pass
    if "```json" in text:
        chunk = text.split("```json", 1)[1].split("```", 1)[0]
        try:
            parsed = json.loads(chunk.strip())
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
    return fallback


def _build_user_text(
    *,
    messages: list[dict[str, str]],
    schema_body: dict[str, Any],
    sample_pdf_note: str | None,
    validation_feedback: dict[str, Any] | None,
) -> str:
    user_parts = [f"CURRENT_SCHEMA_JSON:\n{json.dumps(schema_body, indent=2)}"]
    if sample_pdf_note:
        user_parts.append(f"SAMPLE_PDF_TEXT:\n{sample_pdf_note}")
    if validation_feedback:
        user_parts.append(
            "VALIDATION_FEEDBACK (DSL checker, sample PDF preview, and schema judge — fix issues before proposing schema):\n"
            + json.dumps(validation_feedback, indent=2)
        )
        judge_sum = validation_feedback.get("judge_summary")
        if judge_sum:
            recs = validation_feedback.get("judge_recommendations") or []
            user_parts.append(
                "JUDGE_AGENT_RECOMMENDATIONS:\n"
                + str(judge_sum)
                + ("\n- " + "\n- ".join(str(r) for r in recs) if recs else "")
            )
    transcript: list[str] = []
    for m in messages:
        role = str(m.get("role") or "user").strip().lower()
        content = str(m.get("content") or "").strip()
        if not content:
            continue
        transcript.append(f"{'Assistant' if role == 'assistant' else 'User'}: {content}")
    if transcript:
        user_parts.append("CONVERSATION:\n" + "\n\n".join(transcript))
    return "\n\n".join(p for p in user_parts if p)


def _repair_prompt(errors: list[str], proposed: dict[str, Any]) -> str:
    return (
        "The schema failed validation after automatic normalization.\n"
        f"Errors:\n{json.dumps(errors, indent=2)}\n\n"
        f"Current draft:\n{json.dumps(proposed, indent=2)}\n\n"
        "Fix every error. For open_ended: always set ``extract_prompt``; use ``informative_only: true`` "
        "when the user asked for extraction without validation. "
        "Use ``fields`` with aliases + regex_hint (or ``llm_fallback`` + ``llm_only`` without regex for invoice_number). "
        "Use canonical keys: issue_date, due_date, total_due, invoice_number, recipient_email. "
        "If requirements are ambiguous, ask one clarifying question in your reply before the schema block. "
        "Reply with a short explanation and a corrected ```schema``` block."
    )


class SchemaAgentRunner:
    """Ollama chat with normalize → validate → repair loop."""

    def __init__(self) -> None:
        self._capabilities = get_engine_capabilities()

    async def chat(
        self,
        *,
        messages: list[dict[str, str]],
        schema_body: dict[str, Any],
        sample_pdf_note: str | None = None,
        validation_feedback: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        system = (
            _INSTRUCTION
            + "\n\nWhen VALIDATION_FEEDBACK is present, address DSL errors and preview failures "
            "in your next schema revision.\n\nENGINE_CAPABILITIES_JSON:\n"
            + json.dumps(self._capabilities, indent=2)
        )
        user_text = _build_user_text(
            messages=messages,
            schema_body=schema_body,
            sample_pdf_note=sample_pdf_note,
            validation_feedback=validation_feedback,
        )
        chat_messages: list[dict[str, str]] = [
            {"role": "system", "content": system},
            {"role": "user", "content": user_text},
        ]

        final_text = await ollama_chat(chat_messages, temperature=0.2)
        proposed = normalize_schema_body(
            _apply_transcript_policies(messages, _extract_schema_from_text(final_text, schema_body)),
        )

        notes: list[str] = []
        for attempt in range(_MAX_REPAIR_TURNS):
            validation = validate_schema_body(proposed)
            normalized = validation.get("normalized_body")
            if isinstance(normalized, dict) and normalized:
                proposed = normalized
            if validation.get("ok"):
                if notes:
                    final_text = (
                        final_text.strip()
                        + "\n\n---\n**Schema adjusted for the validation engine:** "
                        + "; ".join(notes)
                    )
                break
            errors = validation.get("errors") or []
            chat_messages.append({"role": "assistant", "content": final_text})
            chat_messages.append({"role": "user", "content": _repair_prompt(errors, proposed)})
            repair_text = await ollama_chat(chat_messages, temperature=0.1)
            final_text = f"{final_text.strip()}\n\n{repair_text.strip()}".strip()
            raw = _extract_schema_from_text(repair_text, proposed)
            proposed = normalize_schema_body(_apply_transcript_policies(messages, raw))
            notes.append(f"repair pass {attempt + 1}")
        else:
            validation = validate_schema_body(proposed)
            normalized = validation.get("normalized_body")
            if isinstance(normalized, dict) and normalized:
                proposed = normalized
            if not validation.get("ok"):
                err_summary = "; ".join(validation.get("errors") or ["unknown"])
                final_text += (
                    f"\n\n**I could not fully fix the schema automatically.** Remaining DSL issues: {err_summary}\n\n"
                    "Can you clarify whether any open-ended fields should affect PASS/FAIL "
                    "(need ``evaluate_prompt``) or are informative-only?"
                )

        return {"reply": final_text.strip(), "schema_body": proposed}
