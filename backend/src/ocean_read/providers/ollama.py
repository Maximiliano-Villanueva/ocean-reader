"""Ollama-backed LLM (validation fallback uses text completion)."""

from __future__ import annotations

import base64
import io
import json
import logging
import re
from typing import Any

import httpx
from PIL import Image

from ocean_read.config import Settings, get_settings

logger = logging.getLogger(__name__)

# Strip optional data-URL prefix (some extractors or browsers produce this shape).
_DATA_URL_RE = re.compile(r"^data:image/[^;]+;base64,", re.IGNORECASE)


def normalize_base64_image_for_ollama(data_b64: str) -> str | None:
    """Decode embedded/PDF image bytes and re-encode as PNG for Ollama vision models.

    PDFs often contain JBIG2, JPEG2000, CCITT, or opaque payloads labeled as
    ``application/octet-stream``. Gemma and other runners then fail with
    ``image: unknown format``. Pillow converts decodable raster formats into PNG
    bytes Ollama reliably accepts (`Ollama vision docs`_).

    Returns ``None`` if bytes are missing or cannot be opened as an image.

    .. _Ollama vision docs: https://docs.ollama.com/capabilities/vision
    """
    if not (data_b64 or "").strip():
        return None
    s = data_b64.strip()
    if s.startswith("data:"):
        s = _DATA_URL_RE.sub("", s)
    try:
        raw = base64.b64decode(s, validate=False)
    except Exception:
        return None
    if not raw:
        return None
    try:
        im = Image.open(io.BytesIO(raw))
        im.load()
    except Exception:
        return None
    try:
        if im.mode == "RGBA":
            background = Image.new("RGB", im.size, (255, 255, 255))
            background.paste(im, mask=im.split()[3])
            im = background
        elif im.mode != "RGB":
            im = im.convert("RGB")
        out = io.BytesIO()
        im.save(out, format="PNG")
        return base64.b64encode(out.getvalue()).decode("ascii")
    except Exception:
        return None


def loads_json_maybe_with_fence(text: str) -> dict[str, Any] | list[Any]:
    raw = text.strip()
    if "```" in raw:
        start = raw.find("```") + 3
        rest = raw[start:]
        if "\n" in rest:
            rest = rest[rest.find("\n") + 1 :]
        end_fence = rest.rfind("```")
        if end_fence >= 0:
            rest = rest[:end_fence].strip()
        raw = rest
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Could not parse JSON from model output: {e}: {text[:500]}") from e


class OllamaLLMClient:
    """Text + multimodal completions via /api/generate."""

    def __init__(self, settings: Settings | None = None, client: httpx.AsyncClient | None = None):
        self._settings = settings or get_settings()
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(base_url=self._settings.ollama_base_url, timeout=1200.0)

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def complete(self, system_prompt: str, user_prompt: str, *, temperature: float = 0.2) -> str:
        payload: dict[str, Any] = {
            "model": self._settings.llm_model,
            "prompt": user_prompt.strip(),
            "stream": False,
            "options": {"temperature": temperature},
        }
        if system_prompt.strip():
            payload["system"] = system_prompt.strip()
        return await self._generate(payload)

    async def complete_with_images(
        self,
        user_prompt: str,
        images_base64: list[str],
        *,
        system_prompt: str = "",
        max_tokens: int | None = None,
    ) -> str:
        normalized: list[str] = []
        for raw_b64 in images_base64:
            n = normalize_base64_image_for_ollama(raw_b64)
            if n:
                normalized.append(n)
            else:
                logger.warning("Skipping an image: could not decode or convert to PNG for Ollama vision.")
        if not normalized:
            raise ValueError(
                "No vision images could be converted to PNG for the model. "
                "PDF-embedded formats (e.g. JBIG2, JPEG2000) may be unsupported—re-export the PDF "
                "or use image-only pages. Pull and use a vision-capable tag such as `gemma4:e4b` per "
                "https://ollama.com/library/gemma4:e4b"
            )
        opts: dict[str, Any] = {"temperature": 0.15}
        if max_tokens is not None:
            opts["num_predict"] = int(max_tokens)
        payload: dict[str, Any] = {
            "model": self._settings.llm_model,
            "prompt": user_prompt.strip(),
            "images": normalized,
            "stream": False,
            "options": opts,
        }
        if system_prompt.strip():
            payload["system"] = system_prompt.strip()
        return await self._generate(payload)

    async def _generate(self, payload: dict[str, Any]) -> str:
        r = await self._client.post("/api/generate", json=payload)
        if r.status_code >= 400:
            try:
                body = r.json()
                msg = body.get("error", r.text)
            except Exception:
                msg = r.text
            raise RuntimeError(f"Ollama generate failed ({r.status_code}): {msg}. Pull `{self._settings.llm_model}`.")
        body = r.json()
        txt = body.get("response", "")
        return "" if txt is None else str(txt)
