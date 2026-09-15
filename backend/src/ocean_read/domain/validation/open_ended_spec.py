"""
Open-ended schema field specs (DSL v3): LLM extraction/evaluation alongside strict fields.

Strict ``fields`` continue to use the deterministic engine. Entries under ``open_ended``
carry natural-language prompts; the pipeline calls an LLM with ``pdf_blocks`` text (M1 layout).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

EvaluationTag = Literal["pass", "fail", "ambiguous"]

DEFAULT_EVALUATION_TAGS: tuple[EvaluationTag, ...] = ("pass", "fail", "ambiguous")


@dataclass(frozen=True)
class OpenEndedFieldSpec:
    """One open-ended field in the schema body."""

    name: str
    extract_prompt: str
    evaluate_prompt: str | None
    informative_only: bool
    link_evidence: bool
    evaluation_tags: tuple[EvaluationTag, ...]
    depends_on_fields: tuple[str, ...]


def parse_open_ended_specs(body: dict[str, Any]) -> list[OpenEndedFieldSpec]:
    """Parse ``body['open_ended']``; ignore malformed entries (validation catches errors earlier)."""

    raw = body.get("open_ended")
    if not raw or not isinstance(raw, dict):
        return []
    out: list[OpenEndedFieldSpec] = []
    for name, spec in raw.items():
        if not isinstance(spec, dict):
            continue
        extract = str(spec.get("extract_prompt") or "").strip()
        if not extract:
            continue
        eval_p = spec.get("evaluate_prompt")
        evaluate_prompt = str(eval_p).strip() if eval_p else None
        informative = bool(spec.get("informative_only", False))
        link_evidence = bool(spec.get("link_evidence", not informative))
        tags_raw = spec.get("evaluation_tags")
        tags: tuple[EvaluationTag, ...] = DEFAULT_EVALUATION_TAGS
        if isinstance(tags_raw, list) and tags_raw:
            parsed: list[EvaluationTag] = []
            for t in tags_raw:
                s = str(t).strip().lower()
                if s in ("pass", "fail", "ambiguous"):
                    parsed.append(s)  # type: ignore[arg-type]
            if parsed:
                tags = tuple(parsed)
        deps_raw = spec.get("depends_on_fields")
        deps: tuple[str, ...] = ()
        if isinstance(deps_raw, list):
            deps = tuple(str(x) for x in deps_raw if str(x).strip())
        out.append(
            OpenEndedFieldSpec(
                name=str(name),
                extract_prompt=extract,
                evaluate_prompt=evaluate_prompt,
                informative_only=informative,
                link_evidence=link_evidence,
                evaluation_tags=tags,
                depends_on_fields=deps,
            )
        )
    return out
