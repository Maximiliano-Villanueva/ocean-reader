"""
Multimodal LLM extraction fallback when PDF layout text is missing (scanned/image pages).

Uses Ollama vision (``gemma4:e4b``) with schema field list; outputs ``ExtractionCandidate`` with ``source='vision'``.
Temperature 0 per ADR 003. Does not perform PASS/FAIL — only field discovery.
"""

from __future__ import annotations

import logging
from typing import Any

from ocean_read.domain.validation.mapping import FieldEntry
from ocean_read.domain.validation.pdf_page_images import PageImage, page_bbox, render_pdf_page_images
from ocean_read.domain.validation.resolution import ExtractionCandidate
from ocean_read.providers.ollama import OllamaLLMClient, loads_json_maybe_with_fence

logger = logging.getLogger(__name__)

_VISION_SOURCE = "vision"
_VISION_CONFIDENCE = 0.42


def missing_required_field_names(
    field_map: dict[str, FieldEntry],
    schema_fields: dict[str, Any],
) -> list[str]:
    """Schema fields marked required that have no extraction candidate."""

    out: list[str] = []
    for name, spec in schema_fields.items():
        if not isinstance(spec, dict):
            continue
        if not spec.get("required"):
            continue
        entry = field_map.get(name)
        if entry is None or entry.status == "missing":
            out.append(name)
    return out


def extraction_failure_on_fail(
    errors: tuple[Any, ...],
    field_map: dict[str, FieldEntry],
    schema_fields: dict[str, Any],
) -> bool:
    """True when FAIL is plausibly due to missing extraction (not range violations only)."""

    if any(getattr(e, "rule", None) == "required" for e in errors):
        return True
    return len(missing_required_field_names(field_map, schema_fields)) > 0


def _field_specs_for_prompt(schema_fields: dict[str, Any]) -> list[dict[str, str]]:
    specs: list[dict[str, str]] = []
    for name, raw in schema_fields.items():
        if not isinstance(raw, dict):
            continue
        parts = [f"name: {name}", f"type: {raw.get('type', 'string')}"]
        if raw.get("required"):
            parts.append("required: true")
        if raw.get("min") is not None or raw.get("max") is not None:
            parts.append(f"range: {raw.get('min')} – {raw.get('max')}")
        aliases = raw.get("aliases") or []
        if aliases:
            parts.append(f"aliases: {', '.join(str(a) for a in aliases)}")
        specs.append({"name": name, "summary": " · ".join(parts)})
    return specs


def _build_system_prompt() -> str:
    return (
        "You extract structured field values from document page images. "
        "Respond with JSON only: "
        '{"fields": {"<field_name>": <value or null>, ...}}. '
        "Use null when not visible. Numbers as JSON numbers; dates/strings as strings. "
        "Do not invent values."
    )


def _build_user_prompt(field_specs: list[dict[str, str]], page: int) -> str:
    lines = [f"Document page {page}. Extract these schema fields if visible:"]
    for s in field_specs:
        lines.append(f"- {s['name']}: {s['summary']}")
    return "\n".join(lines)


def _parse_vision_fields(data: Any, schema_fields: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(data, dict):
        return {}
    fields = data.get("fields")
    if not isinstance(fields, dict):
        return {}
    out: dict[str, Any] = {}
    for key in schema_fields:
        if key in fields:
            out[key] = fields[key]
    return out


async def extract_fields_via_ollama_vision(
    pdf_bytes: bytes,
    schema_fields: dict[str, Any],
    *,
    client: OllamaLLMClient,
    max_pages: int = 4,
) -> list[ExtractionCandidate]:
    """Ollama vision: one page image per request, merge field hypotheses."""

    if not schema_fields:
        return []
    pages = render_pdf_page_images(pdf_bytes, max_pages=max_pages)
    if not pages:
        return []

    field_specs = _field_specs_for_prompt(schema_fields)
    system = _build_system_prompt()
    merged: dict[str, Any] = {}

    for pg in pages:
        user_text = _build_user_prompt(field_specs, pg.page)
        try:
            raw = await client.complete_with_images(
                user_text,
                [pg.base64],
                system_prompt=system,
                max_tokens=2048,
            )
            data = loads_json_maybe_with_fence(raw)
            if isinstance(data, dict):
                parsed = _parse_vision_fields(data, schema_fields)
                for k, v in parsed.items():
                    if v is not None and k not in merged:
                        merged[k] = v
        except Exception as exc:
            logger.info("Ollama vision page %s skipped: %s", pg.page, exc)

    return _candidates_from_values(merged, schema_fields, pdf_bytes, pages)


def _candidates_from_values(
    values: dict[str, Any],
    schema_fields: dict[str, Any],
    pdf_bytes: bytes,
    pages: list[PageImage],
) -> list[ExtractionCandidate]:
    if not values:
        return []
    page = pages[0].page if pages else 1
    try:
        bbox = page_bbox(page, pdf_bytes)
    except Exception:
        bbox = None
    out: list[ExtractionCandidate] = []
    for field, value in values.items():
        if value is None:
            continue
        out.append(
            ExtractionCandidate(
                field=field,
                value=value,
                source=_VISION_SOURCE,
                confidence=_VISION_CONFIDENCE,
                block_id=f"vision-p{page}",
                page=page,
                evidence_text=f"vision extraction (page {page})",
                bbox=bbox,
                section_label="vision",
            )
        )
    return out


async def vision_fallback_candidates(
    pdf_bytes: bytes,
    schema_fields: dict[str, Any],
    *,
    max_pages: int | None = None,
) -> list[ExtractionCandidate]:
    """Extract via Ollama vision (``gemma4:e4b``)."""

    from ocean_read.config import get_settings

    pages_cap = max_pages if max_pages is not None else get_settings().validation_llm_vision_max_pages

    ollama = OllamaLLMClient()
    try:
        return await extract_fields_via_ollama_vision(
            pdf_bytes, schema_fields, client=ollama, max_pages=pages_cap
        )
    except Exception as exc:
        logger.info("Ollama vision unavailable: %s", exc)
        return []
    finally:
        await ollama.aclose()
