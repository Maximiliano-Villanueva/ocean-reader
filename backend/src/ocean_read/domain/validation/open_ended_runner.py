"""
Run open-ended schema fields: LLM extraction (and optional evaluation) over ``pdf_blocks`` text.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Literal

from ocean_read.domain.validation.open_ended_spec import (
    DEFAULT_EVALUATION_TAGS,
    EvaluationTag,
    OpenEndedFieldSpec,
    parse_open_ended_specs,
)
from ocean_read.domain.validation.pdf_blocks import TextBlock
from ocean_read.providers.ollama import OllamaLLMClient

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OpenEndedEvidence:
    """PDF evidence link for an open-ended extraction."""

    text: str
    block_id: str
    page: int
    bbox: list[float] | None


@dataclass(frozen=True)
class OpenEndedFieldResult:
    """Outcome for one open-ended field after pipeline LLM pass."""

    field: str
    extracted_value: str | None
    evaluation: EvaluationTag | None
    informative_only: bool
    evidence: tuple[OpenEndedEvidence, ...]


def _blocks_text(blocks: list[TextBlock], *, max_chars: int = 14000) -> str:
    lines: list[str] = []
    for b in blocks[:120]:
        prefix = f"[p{b.page} #{b.id}] "
        lines.append(prefix + (b.text or "").strip())
    blob = "\n".join(lines)
    return blob[:max_chars]


def _find_evidence_snippets(blocks: list[TextBlock], snippet: str, *, max_items: int = 3) -> tuple[OpenEndedEvidence, ...]:
    needle = (snippet or "").strip().lower()
    if not needle or len(needle) < 8:
        return ()
    out: list[OpenEndedEvidence] = []
    for b in blocks:
        if needle in (b.text or "").lower():
            bb = list(b.bbox) if b.bbox and len(b.bbox) >= 4 else None
            out.append(
                OpenEndedEvidence(
                    text=(b.text or "")[:500],
                    block_id=b.id,
                    page=b.page,
                    bbox=bb,
                )
            )
            if len(out) >= max_items:
                break
    return tuple(out)


_EXTRACT_SYSTEM = (
    "You extract information from document text blocks. "
    "Respond with JSON only: "
    '{"value": string|null, "evidence_quote": string|null}. '
    "evidence_quote must be a short verbatim substring from the document when possible."
)

_EVAL_SYSTEM_TEMPLATE = (
    "You evaluate extracted document information. "
    "Respond with JSON only: "
    '{{"evaluation": "<tag>", "rationale": string}}. '
    "Allowed evaluation tags: {tags}. "
    "Use ambiguous when evidence conflicts or is insufficient."
)


async def run_open_ended_fields(
    *,
    schema_body: dict[str, Any],
    blocks: list[TextBlock],
    resolved_strict: dict[str, Any],
    client: OllamaLLMClient | None,
    enabled: bool,
    document_text: str | None = None,
) -> tuple[OpenEndedFieldResult, ...]:
    """Execute all ``open_ended`` specs when LLM is enabled; otherwise return empty."""

    specs = parse_open_ended_specs(schema_body)
    if not specs or not enabled or client is None:
        return ()
    doc_text = (document_text or "").strip() or _blocks_text(blocks)
    if not doc_text.strip():
        return ()

    results: list[OpenEndedFieldResult] = []
    for spec in specs:
        try:
            results.append(
                await _run_one(spec, doc_text=doc_text, blocks=blocks, resolved_strict=resolved_strict, client=client)
            )
        except Exception as exc:
            logger.info("Open-ended field %s skipped: %s", spec.name, exc)
            results.append(
                OpenEndedFieldResult(
                    field=spec.name,
                    extracted_value=None,
                    evaluation="ambiguous" if not spec.informative_only else None,
                    informative_only=spec.informative_only,
                    evidence=(),
                )
            )
    return tuple(results)


async def _run_one(
    spec: OpenEndedFieldSpec,
    *,
    doc_text: str,
    blocks: list[TextBlock],
    resolved_strict: dict[str, Any],
    client: OllamaLLMClient,
) -> OpenEndedFieldResult:
    user_extract = (
        f"Field: {spec.name}\n"
        f"Task: {spec.extract_prompt}\n\n"
        f"Document blocks:\n{doc_text}\n"
    )
    raw_extract = await client.chat_json(_EXTRACT_SYSTEM, user_extract, temperature=0.15)
    value: str | None = None
    quote: str | None = None
    if isinstance(raw_extract, dict):
        v = raw_extract.get("value")
        value = None if v is None else str(v)
        q = raw_extract.get("evidence_quote")
        quote = None if q is None else str(q)

    evidence: tuple[OpenEndedEvidence, ...] = ()
    if spec.link_evidence and quote:
        evidence = _find_evidence_snippets(blocks, quote)

    evaluation: EvaluationTag | None = None
    if not spec.informative_only and spec.evaluate_prompt:
        ctx_parts = [f"Extracted value for {spec.name}: {value!r}"]
        for dep in spec.depends_on_fields:
            if dep in resolved_strict:
                ctx_parts.append(f"Strict field {dep}: {resolved_strict[dep]!r}")
        tags = ", ".join(spec.evaluation_tags or DEFAULT_EVALUATION_TAGS)
        system = _EVAL_SYSTEM_TEMPLATE.format(tags=tags)
        user_eval = (
            f"{chr(10).join(ctx_parts)}\n\n"
            f"Evaluation task: {spec.evaluate_prompt}\n\n"
            f"Document blocks:\n{doc_text[:8000]}\n"
        )
        raw_eval = await client.chat_json(system, user_eval, temperature=0.15)
        if isinstance(raw_eval, dict):
            tag = str(raw_eval.get("evaluation") or "").strip().lower()
            if tag in spec.evaluation_tags:
                evaluation = tag  # type: ignore[assignment]
            elif tag in DEFAULT_EVALUATION_TAGS:
                evaluation = tag  # type: ignore[assignment]
            else:
                evaluation = "ambiguous"

    return OpenEndedFieldResult(
        field=spec.name,
        extracted_value=value,
        evaluation=evaluation,
        informative_only=spec.informative_only,
        evidence=evidence,
    )


def merge_open_ended_into_status(
    base_status: Literal["PASS", "FAIL", "AMBIGUOUS"],
    results: tuple[OpenEndedFieldResult, ...],
) -> Literal["PASS", "FAIL", "AMBIGUOUS"]:
    """Promote status when a non-informative open-ended evaluation fails or is ambiguous."""

    status = base_status
    for r in results:
        if r.informative_only or r.evaluation is None:
            continue
        if r.evaluation == "fail":
            return "FAIL"
        if r.evaluation == "ambiguous" and status == "PASS":
            return "AMBIGUOUS"
    return status
