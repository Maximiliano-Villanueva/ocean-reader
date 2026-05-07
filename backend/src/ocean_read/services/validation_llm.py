"""Internal LLM fallback for wine field extraction — lower priority than regex/layout."""

from __future__ import annotations

import logging
from typing import Any

from ocean_read.domain.validation.pdf_blocks import TextBlock
from ocean_read.domain.validation.resolution import ExtractionCandidate
from ocean_read.providers.ollama import OllamaLLMClient, loads_json_maybe_with_fence

logger = logging.getLogger(__name__)

_SYSTEM = (
    "Extract three numeric fields from the wine lab report text. "
    'Respond with JSON only: {"ph": number|null, "alcohol": number|null, "quality": number|null}. '
    "Use null if unknown. No prose."
)


async def llm_fallback_wine_fields(
    blocks: list[TextBlock],
    *,
    client: OllamaLLMClient,
) -> list[ExtractionCandidate]:
    if not blocks:
        return []
    text = "\n".join(b.text for b in blocks[:80])[:12000]
    user = f"Report text:\n{text}\n"
    try:
        raw = await client.complete(_SYSTEM, user, temperature=0.0)
        data: Any = loads_json_maybe_with_fence(raw)
    except Exception as e:
        logger.info("Validation LLM fallback skipped: %s", e)
        return []
    if not isinstance(data, dict):
        return []
    anchor = blocks[0]
    out: list[ExtractionCandidate] = []
    for field in ("ph", "alcohol", "quality"):
        v = data.get(field)
        if v is None:
            continue
        try:
            fv = float(v)
        except (TypeError, ValueError):
            continue
        out.append(
            ExtractionCandidate(
                field=field,
                value=fv,
                source="llm",
                confidence=0.4,
                block_id=anchor.id,
                page=anchor.page,
                evidence_text=text[:800],
                bbox=anchor.bbox,
                section_label=anchor.section_label,
            )
        )
    return out
