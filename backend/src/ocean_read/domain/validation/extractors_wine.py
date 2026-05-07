"""Wine QA-style ensemble extractors: regex and layout heuristics over ``TextBlock``s."""

from __future__ import annotations

import re

from ocean_read.domain.validation.pdf_blocks import TextBlock
from ocean_read.domain.validation.resolution import ExtractionCandidate

_PH_RE = re.compile(r"(?i)p[hH]\s*[:=]\s*([\d.]+)")
_ALCOHOL_RE = re.compile(r"(?i)alcohol\s*[:=]\s*([\d.]+)\s*%?")
_QUALITY_RE = re.compile(r"(?i)quality\s*[:=]\s*([\d.]+)")
_FLOAT_RE = re.compile(r"[\d.]+")


def _safe_float(s: str) -> float | None:
    try:
        return float(s)
    except ValueError:
        return None


def extract_regex_wine(blocks: list[TextBlock]) -> list[ExtractionCandidate]:
    """High-confidence patterns anchored to each block (evidence = matched span)."""

    out: list[ExtractionCandidate] = []
    for b in blocks:
        t = b.text
        for field, rx, conf in (
            ("ph", _PH_RE, 0.95),
            ("alcohol", _ALCOHOL_RE, 0.95),
            ("quality", _QUALITY_RE, 0.95),
        ):
            m = rx.search(t)
            if not m:
                continue
            raw = m.group(1)
            val = _safe_float(raw)
            if val is None:
                continue
            snippet = m.group(0).strip()
            out.append(
                ExtractionCandidate(
                    field=field,
                    value=val,
                    source="regex",
                    confidence=conf,
                    block_id=b.id,
                    page=b.page,
                    evidence_text=snippet or t[:280],
                    bbox=b.bbox,
                    section_label=b.section_label,
                )
            )
    return out


def extract_layout_wine(blocks: list[TextBlock]) -> list[ExtractionCandidate]:
    """Lower-confidence line heuristics when labels appear without strict regex match."""

    out: list[ExtractionCandidate] = []
    for b in blocks:
        for line in b.text.splitlines():
            lt = line.strip()
            if not lt:
                continue
            lower = lt.lower()
            # Alcohol line: word alcohol + a number on same line
            if "alcohol" in lower:
                nums = [x for x in _FLOAT_RE.findall(lt) if _safe_float(x) is not None]
                if nums:
                    v = _safe_float(nums[-1])
                    if v is not None:
                        out.append(
                            ExtractionCandidate(
                                field="alcohol",
                                value=v,
                                source="layout",
                                confidence=0.55,
                                block_id=b.id,
                                page=b.page,
                                evidence_text=lt[:280],
                                bbox=b.bbox,
                                section_label=b.section_label,
                            )
                        )
            if lower.startswith("ph") or " ph " in f" {lower} ":
                nums = [x for x in _FLOAT_RE.findall(lt) if _safe_float(x) is not None]
                if nums:
                    v = _safe_float(nums[0])
                    if v is not None and 0 < v < 14:
                        out.append(
                            ExtractionCandidate(
                                field="ph",
                                value=v,
                                source="layout",
                                confidence=0.5,
                                block_id=b.id,
                                page=b.page,
                                evidence_text=lt[:280],
                                bbox=b.bbox,
                                section_label=b.section_label,
                            )
                        )
            if "quality" in lower:
                nums = [x for x in _FLOAT_RE.findall(lt) if _safe_float(x) is not None]
                if nums:
                    v = _safe_float(nums[-1])
                    if v is not None:
                        out.append(
                            ExtractionCandidate(
                                field="quality",
                                value=v,
                                source="layout",
                                confidence=0.5,
                                block_id=b.id,
                                page=b.page,
                                evidence_text=lt[:280],
                                bbox=b.bbox,
                                section_label=b.section_label,
                            )
                        )
    return out


def ensemble_wine_extractors(blocks: list[TextBlock]) -> list[ExtractionCandidate]:
    """Regex + layout candidates (LLM is appended by the application layer)."""

    return extract_regex_wine(blocks) + extract_layout_wine(blocks)
