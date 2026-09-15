"""
Analyze Docling embedded pictures with the vision LLM when ``read_images`` is enabled.
"""

from __future__ import annotations

import logging

from ocean_read.domain.validation.docling_parse import DoclingPictureRef
from ocean_read.providers.ollama import OllamaLLMClient

logger = logging.getLogger(__name__)

_SYSTEM = (
    "You describe embedded images from a business document (invoice, certificate, etc.). "
    "Extract any visible text, numbers, logos, stamps, or tables. Be factual and concise."
)


async def analyze_docling_pictures(
    pictures: list[DoclingPictureRef],
    *,
    client: OllamaLLMClient,
) -> str:
    """Return markdown sections appended to the document view for LLM extraction."""

    sections: list[str] = []
    for pic in pictures:
        if not pic.image_base64_png:
            continue
        prompt = (
            f"Describe this embedded image from page {pic.page}. "
            "List all readable text and explain what the image shows."
        )
        try:
            analysis = await client.complete_with_images(
                prompt,
                [pic.image_base64_png],
                system_prompt=_SYSTEM,
            )
        except Exception as exc:
            logger.info("Picture %s vision analysis skipped: %s", pic.id, exc)
            continue
        cap = f" ({pic.caption})" if pic.caption else ""
        sections.append(f"## Embedded image {pic.id}{cap} — page {pic.page}\n\n{analysis.strip()}")
    return "\n\n".join(sections)
